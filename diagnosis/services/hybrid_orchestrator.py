import hashlib
import os
import re
import time
from typing import Any, Dict, Generator, List, Tuple

from diagnosis.ml_models.med42_service import med42_service

from .medication_safety import MedicationSafetyEngine
from .watsonx_validator import WatsonxValidator


class HybridDiagnosisOrchestrator:
    """Med42 primary reasoning + watsonx secondary validation orchestration."""

    def __init__(self) -> None:
        self.validator = WatsonxValidator()
        self.medication_safety = MedicationSafetyEngine()
        self.cache_ttl_seconds = int(os.environ.get('HYBRID_CACHE_TTL_SECONDS', '300'))
        self.cache_max_items = int(os.environ.get('HYBRID_CACHE_MAX_ITEMS', '128'))
        self.feedback_hint_window = int(os.environ.get('HYBRID_FEEDBACK_HINT_WINDOW', '180'))
        self.feedback_hint_limit = int(os.environ.get('HYBRID_FEEDBACK_HINT_LIMIT', '3'))
        self._cache: Dict[str, Dict[str, Any]] = {}

    def analyze(self, symptoms: str, clinical_notes: str = '') -> Dict[str, Any]:
        done_payload: Dict[str, Any] = {}
        for event in self.stream_analysis(symptoms, clinical_notes, include_tokens=False):
            if event.get('event') == 'done':
                done_payload = event.get('data', {})
                break
        return done_payload

    def stream_analysis(
        self,
        symptoms: str,
        clinical_notes: str = '',
        include_tokens: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        symptoms = (symptoms or '').strip()
        clinical_notes = (clinical_notes or '').strip()

        if not symptoms:
            payload = {
                'result': self._empty_standardized('Symptoms are required'),
                'ai_analysis': self._empty_compatibility('Symptoms are required'),
                'meta': {'cache_hit': False, 'validator_invoked': False},
            }
            yield {'event': 'error', 'data': {'message': 'Symptoms are required'}}
            yield {'event': 'done', 'data': payload}
            return

        cache_key = self._build_cache_key(symptoms, clinical_notes)
        cached = self._get_cached(cache_key)
        if cached:
            yield {'event': 'status', 'data': {'stage': 'cache', 'message': 'Using cached analysis...'}}
            if include_tokens:
                for token in self._tokenize_for_stream(cached['ai_analysis'].get('clinical_reasoning', '')):
                    yield {'event': 'token', 'data': {'stage': 'response', 'text': token}}
            yield {'event': 'done', 'data': {**cached, 'meta': {**cached.get('meta', {}), 'cache_hit': True}}}
            return

        yield {'event': 'status', 'data': {'stage': 'intake', 'message': 'Analyzing symptoms...'}}
        patient_facts = self._build_patient_facts(symptoms, clinical_notes)

        feedback_hints = self._fetch_feedback_hints(symptoms, clinical_notes)
        model_notes = clinical_notes
        if feedback_hints:
            yield {
                'event': 'status',
                'data': {
                    'stage': 'feedback',
                    'message': f'Applying {len(feedback_hints)} doctor feedback hint(s)...',
                },
            }
            model_notes = self._append_feedback_hints_to_notes(clinical_notes, feedback_hints)
            patient_facts['feedback_hints'] = [hint.get('summary', '') for hint in feedback_hints]

        yield {'event': 'status', 'data': {'stage': 'red_flags', 'message': 'Checking red flags...'}}
        med42_result = self._run_med42(symptoms, model_notes)

        if med42_result.get('error'):
            error_text = str(med42_result.get('error')).strip() or 'Primary model analysis failed'
            payload = {
                'result': self._empty_standardized(error_text),
                'ai_analysis': self._empty_compatibility(error_text),
                'meta': {
                    'cache_hit': False,
                    'validator_invoked': False,
                    'validator_status': 'skipped',
                    'token_optimized': True,
                },
            }
            if include_tokens:
                for token in self._tokenize_for_stream(error_text):
                    yield {'event': 'token', 'data': {'stage': 'response', 'text': token}}
            yield {'event': 'done', 'data': payload}
            return

        yield {'event': 'status', 'data': {'stage': 'differential', 'message': 'Generating differential...'}}
        should_validate = self._should_validate(med42_result)

        validator_result = {
            'validator_status': 'skipped',
            'safety_passed': True,
            'issues': [],
            'hallucination_flags': [],
            'standardized_output': None,
            'message': 'validator not needed for this case',
        }

        if should_validate:
            yield {
                'event': 'status',
                'data': {'stage': 'validation', 'message': 'Validating safety with secondary model...'},
            }
            validator_result = self.validator.validate(patient_facts, med42_result)
            yield {
                'event': 'validation',
                'data': {
                    'stage': 'validation',
                    'validator_status': validator_result.get('validator_status', 'unknown'),
                    'safety_passed': validator_result.get('safety_passed', False),
                    'issues': validator_result.get('issues', []),
                },
            }

        yield {
            'event': 'status',
            'data': {'stage': 'format', 'message': 'Formatting final clinical output...'},
        }

        standardized = self._standardize_output(med42_result, validator_result, patient_facts)
        compatibility = self._build_compatibility_output(
            standardized,
            med42_result,
            validator_result,
            patient_facts,
            feedback_hints,
        )

        payload = {
            'result': standardized,
            'ai_analysis': compatibility,
            'meta': {
                'cache_hit': False,
                'validator_invoked': should_validate,
                'validator_status': validator_result.get('validator_status', 'skipped'),
                'token_optimized': True,
            },
        }

        self._set_cached(cache_key, payload)

        if include_tokens:
            for token in self._tokenize_for_stream(compatibility.get('clinical_reasoning', '')):
                yield {'event': 'token', 'data': {'stage': 'response', 'text': token}}

        yield {'event': 'done', 'data': payload}

    def _run_med42(self, symptoms: str, clinical_notes: str) -> Dict[str, Any]:
        if med42_service is None:
            return {
                'error': 'Med42 is not configured. Set HF_TOKEN environment variable.',
                'confidence_score': 0.0,
                'suggested_diagnoses': [],
                'keywords': [],
                'interpretation': 'Analysis unavailable',
                'clinical_reasoning': '',
                'summary': '',
                'recommendations': [],
                'medications': [],
                'red_flag_analysis': {'has_red_flags': False, 'urgency_level': 'UNKNOWN', 'detected_flags': []},
            }

        try:
            return med42_service.analyze_symptoms(symptoms, clinical_notes)
        except Exception as exc:
            return {
                'error': f'Med42 analysis failed: {exc}',
                'confidence_score': 0.0,
                'suggested_diagnoses': [],
                'keywords': [],
                'interpretation': 'Analysis unavailable',
                'clinical_reasoning': '',
                'summary': '',
                'recommendations': [],
                'medications': [],
                'red_flag_analysis': {'has_red_flags': False, 'urgency_level': 'UNKNOWN', 'detected_flags': []},
            }

    def _build_patient_facts(self, symptoms: str, clinical_notes: str) -> Dict[str, Any]:
        normalized_symptoms = self._normalize_common_terms(symptoms)
        normalized_notes = self._normalize_common_terms(clinical_notes)
        merged = f"{normalized_symptoms}\n{normalized_notes}".strip()
        normalized = re.sub(r'\s+', ' ', merged)
        symptom_chunks = re.split(r'[\n,;.]', normalized_symptoms)
        symptoms_list = []
        seen = set()
        for chunk in symptom_chunks:
            term = re.sub(r'\s+', ' ', chunk).strip().lower()
            if len(term) < 3 or term in seen:
                continue
            seen.add(term)
            symptoms_list.append(term)
            if len(symptoms_list) >= 14:
                break

        duration_matches = re.findall(r'\b\d+\s*(?:day|days|week|weeks|month|months|year|years)\b', merged.lower())

        red_flag_cues = []
        red_flag_terms = [
            'chest pain',
            'shortness of breath',
            'hemoptysis',
            'coughing blood',
            'altered mental status',
            'severe headache',
            'nose bleed',
            'epistaxis',
        ]
        lowered = merged.lower()
        for item in red_flag_terms:
            if item in lowered:
                red_flag_cues.append(item)

        return {
            'sx': symptoms_list,
            'dur': duration_matches[:6],
            'rf': red_flag_cues[:6],
            'notes': normalized[:700],
        }

    def _normalize_common_terms(self, text: str) -> str:
        value = re.sub(r'\s+', ' ', str(text or '').strip())
        if not value:
            return ''

        replacements = [
            (r'\bsakit\s+ng\s+katawan\b', 'body aches'),
            (r'\bpananakit\s+ng\s+katawan\b', 'body aches'),
            (r'\binuubo\b', 'cough'),
            (r'\bubo\b', 'cough'),
            (r'\bsipon\b', 'runny nose'),
            (r'\blagnat\b', 'fever'),
            (r'\bnilalagnat\b', 'fever'),
            (r'\bmasakit\s+ulo\b', 'headache'),
        ]
        for pattern, replacement in replacements:
            value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
        return value

    def _should_validate(self, med42_result: Dict[str, Any]) -> bool:
        red_flag_analysis = med42_result.get('red_flag_analysis', {})
        confidence_score = float(med42_result.get('confidence_score', 0) or 0)
        has_primary = bool(med42_result.get('suggested_diagnoses'))
        validation_mode = os.environ.get('HYBRID_VALIDATION_MODE', 'always').strip().lower()

        if med42_result.get('error'):
            return False
        if not self.validator.is_configured:
            return False
        if validation_mode in ['always', 'force', 'on']:
            return True
        if validation_mode in ['never', 'off']:
            return False
        if red_flag_analysis.get('has_red_flags'):
            return True
        if confidence_score < 0.78:
            return True
        if not has_primary:
            return True
        return False

    def _standardize_output(
        self,
        med42_result: Dict[str, Any],
        validator_result: Dict[str, Any],
        patient_facts: Dict[str, Any],
    ) -> Dict[str, Any]:
        suggested = med42_result.get('suggested_diagnoses', [])
        primary = ''
        if isinstance(suggested, list) and suggested:
            primary = str(suggested[0].get('term', '')).strip()

        differential = []
        for item in suggested[:5]:
            term = str(item.get('term', '')).strip()
            if term:
                differential.append(term)

        red_flags = []
        red_flag_analysis = med42_result.get('red_flag_analysis', {})
        for item in red_flag_analysis.get('detected_flags', [])[:5]:
            flag_name = str(item.get('flag', '')).replace('_', ' ').strip()
            keyword = str(item.get('keyword', '')).strip()
            if flag_name and keyword:
                red_flags.append(f"{flag_name}: {keyword}")
            elif flag_name:
                red_flags.append(flag_name)

        medications = []
        for med in med42_result.get('medications', [])[:5]:
            med_entry = {
                'name': str(med.get('medication_name', '')).strip(),
                'dosage': str(med.get('dosage', '')).strip(),
                'frequency': str(med.get('frequency', '')).strip(),
                'duration': str(med.get('duration', '')).strip(),
                'instructions': str(med.get('instructions', '')).strip(),
            }
            medications.append(self._normalize_medication_entry(med_entry))

        confidence_score = self._safe_confidence(med42_result.get('confidence_score', 0))
        safety_issues = validator_result.get('issues', []) if isinstance(validator_result, dict) else []
        hallucination_flags = (
            validator_result.get('hallucination_flags', []) if isinstance(validator_result, dict) else []
        )
        safety_passed = bool(validator_result.get('safety_passed', not red_flags))

        standardized = {
            'primary_diagnosis': primary,
            'differential_diagnoses': differential,
            'red_flags': red_flags,
            'recommended_workup': self._clean_strings(med42_result.get('recommendations', []), limit=6),
            'medications': medications,
            'confidence_score': confidence_score,
            'safety_assessment': {
                'passed': safety_passed,
                'issues': self._clean_strings(safety_issues, limit=6),
            },
            'validator_notes': str(validator_result.get('message', '')).strip(),
            'summary': str(med42_result.get('summary', '')).strip(),
            'hallucination_flags': self._clean_strings(hallucination_flags, limit=6),
        }

        validator_output = validator_result.get('standardized_output')
        if isinstance(validator_output, dict):
            standardized = self._merge_validator_output(standardized, validator_output)

        medication_context = ' '.join(
            self._clean_strings(
                patient_facts.get('sx', []) + [patient_facts.get('notes', '')],
                limit=18,
            )
        )
        medication_safety = self.medication_safety.assess(standardized.get('medications', []), medication_context)
        standardized['medication_safety'] = medication_safety

        safety_issues = standardized.get('safety_assessment', {}).get('issues', [])
        for alert in medication_safety.get('alerts', [])[:6]:
            if alert.get('severity') not in ['high', 'moderate']:
                continue
            issue_text = (
                f"{alert.get('medication', 'Medication')}: {alert.get('issue', '')} "
                f"Recommendation: {alert.get('recommendation', '')}"
            ).strip()
            if issue_text and issue_text not in safety_issues:
                safety_issues.append(issue_text)
        standardized['safety_assessment']['issues'] = self._clean_strings(safety_issues, limit=8)
        if medication_safety.get('overall_risk') == 'high':
            standardized['safety_assessment']['passed'] = False

        return standardized

    def _merge_validator_output(self, base: Dict[str, Any], validator_output: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)

        validator_primary = str(validator_output.get('primary_diagnosis', '')).strip()
        if validator_primary:
            base_candidates = [merged.get('primary_diagnosis', '')] + merged.get('differential_diagnoses', [])
            if self._matches_any_diagnosis(validator_primary, base_candidates):
                merged['primary_diagnosis'] = validator_primary

        for key in ['summary', 'validator_notes']:
            value = str(validator_output.get(key, '')).strip()
            if value:
                merged[key] = value

        for key, limit in [
            ('differential_diagnoses', 5),
            ('red_flags', 6),
            ('recommended_workup', 6),
            ('hallucination_flags', 6),
        ]:
            cleaned = self._clean_strings(validator_output.get(key, []), limit=limit)
            if cleaned:
                if key == 'differential_diagnoses':
                    existing = [merged.get('primary_diagnosis', '')] + merged.get('differential_diagnoses', [])
                    has_overlap = any(self._matches_any_diagnosis(item, existing) for item in cleaned)
                    if has_overlap or not merged.get('differential_diagnoses'):
                        merged[key] = cleaned
                else:
                    merged[key] = cleaned

        validator_confidence = self._safe_confidence(validator_output.get('confidence_score', merged['confidence_score']))
        merged['confidence_score'] = validator_confidence

        validator_safety = validator_output.get('safety_assessment', {})
        if isinstance(validator_safety, dict):
            merged['safety_assessment'] = {
                'passed': bool(validator_safety.get('passed', merged['safety_assessment'].get('passed', True))),
                'issues': self._clean_strings(validator_safety.get('issues', []), limit=6),
            }

        validator_meds = validator_output.get('medications', [])
        normalized_validator_meds = []
        if isinstance(validator_meds, list):
            for med in validator_meds[:5]:
                if not isinstance(med, dict):
                    continue
                normalized_validator_meds.append(
                    self._normalize_medication_entry({
                        'name': str(med.get('name', med.get('medication_name', ''))).strip(),
                        'dosage': str(med.get('dosage', '')).strip(),
                        'frequency': str(med.get('frequency', '')).strip(),
                        'duration': str(med.get('duration', '')).strip(),
                        'instructions': str(med.get('instructions', '')).strip(),
                    })
                )
        if normalized_validator_meds:
            merged['medications'] = normalized_validator_meds

        return merged

    def _build_compatibility_output(
        self,
        standardized: Dict[str, Any],
        med42_result: Dict[str, Any],
        validator_result: Dict[str, Any],
        patient_facts: Dict[str, Any],
        feedback_hints: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        differential = standardized.get('differential_diagnoses', [])
        suggested = []

        original_scores = {
            str(item.get('term', '')).strip().lower(): self._safe_confidence(item.get('score', 0))
            for item in med42_result.get('suggested_diagnoses', [])
            if isinstance(item, dict)
        }

        for index, term in enumerate(differential[:6]):
            normalized_term = str(term).strip()
            if not normalized_term:
                continue
            key = normalized_term.lower()
            fallback_score = max(0.3, standardized.get('confidence_score', 0.5) - (0.08 * index))
            suggested.append({'term': normalized_term, 'score': original_scores.get(key, fallback_score)})

        reasoning = self._render_reasoning_text(standardized)
        safety_issues = standardized.get('safety_assessment', {}).get('issues', [])
        hallucination_flags = standardized.get('hallucination_flags', [])
        warnings = self._clean_strings(safety_issues + hallucination_flags, limit=8)

        medications = []
        for med in standardized.get('medications', [])[:5]:
            schedule = self._derive_schedule_from_frequency(str(med.get('frequency', '')).strip())
            medications.append(
                {
                    'medication_name': str(med.get('name', '')).strip(),
                    'dosage': str(med.get('dosage', '')).strip(),
                    'frequency': str(med.get('frequency', '')).strip(),
                    'schedule_type': schedule['schedule_type'],
                    'every_hours': schedule['every_hours'],
                    'times_per_day': schedule['times_per_day'],
                    'take_morning': schedule['take_morning'],
                    'take_noon': schedule['take_noon'],
                    'take_evening': schedule['take_evening'],
                    'take_bedtime': schedule['take_bedtime'],
                    'take_with_breakfast': schedule['take_with_breakfast'],
                    'take_with_lunch': schedule['take_with_lunch'],
                    'take_with_dinner': schedule['take_with_dinner'],
                    'duration': str(med.get('duration', '')).strip(),
                    'instructions': str(med.get('instructions', '')).strip(),
                }
            )

        interpretation = str(med42_result.get('interpretation', '')).strip()
        if not interpretation:
            interpretation = (
                'Validated by secondary safety layer'
                if validator_result.get('validator_status') == 'ok'
                else 'Primary model output'
            )

        explainability = self._build_explainability(standardized, med42_result, patient_facts)
        feedback_info = {
            'used_hints': bool(feedback_hints),
            'hint_count': len(feedback_hints),
            'hints': [hint.get('summary', '') for hint in feedback_hints[:3]],
        }

        return {
            'confidence_score': standardized.get('confidence_score', 0.0),
            'suggested_diagnoses': suggested,
            'keywords': self._clean_strings(med42_result.get('keywords', patient_facts.get('sx', [])), limit=14),
            'interpretation': interpretation,
            'clinical_reasoning': reasoning,
            'raw_clinical_reasoning': reasoning,
            'summary': standardized.get('summary', ''),
            'recommendations': self._clean_strings(standardized.get('recommended_workup', []), limit=6),
            'medications': medications,
            'red_flag_analysis': med42_result.get(
                'red_flag_analysis',
                {'has_red_flags': False, 'urgency_level': 'UNKNOWN', 'detected_flags': []},
            ),
            'validation_warning': '; '.join(warnings) if warnings else None,
            'medication_safety': standardized.get('medication_safety', {}),
            'explainability': explainability,
            'feedback_loop_info': feedback_info,
            'validator_info': {
                'validator_status': validator_result.get('validator_status', 'skipped'),
                'safety_passed': standardized.get('safety_assessment', {}).get('passed', True),
                'issues': standardized.get('safety_assessment', {}).get('issues', []),
                'hallucination_flags': standardized.get('hallucination_flags', []),
            },
        }

    def _build_explainability(
        self,
        standardized: Dict[str, Any],
        med42_result: Dict[str, Any],
        patient_facts: Dict[str, Any],
    ) -> Dict[str, Any]:
        features = self._clean_strings(
            med42_result.get('keywords', []) + patient_facts.get('sx', []),
            limit=16,
        )
        workup_items = self._clean_strings(standardized.get('recommended_workup', []), limit=6)
        confidence_score = self._safe_confidence(standardized.get('confidence_score', 0))
        confidence_percent = int(confidence_score * 100)
        differentials = self._clean_strings(standardized.get('differential_diagnoses', []), limit=5)

        confidence_drivers: List[str] = []
        uncertainty_factors: List[str] = []
        missing_data: List[str] = []

        if differentials:
            confidence_drivers.append(f"Primary diagnosis ranked #1 among {len(differentials)} differential candidates.")
        if len(features) >= 3:
            confidence_drivers.append(f"{len(features)} relevant clinical features were detected from symptoms/notes.")
        if standardized.get('red_flags'):
            confidence_drivers.append("Red-flag screening was applied before final ranking.")
        if standardized.get('medication_safety', {}).get('overall_risk') == 'low':
            confidence_drivers.append("Medication safety check found no major conflicts for current suggestions.")

        if confidence_score < 0.75:
            uncertainty_factors.append("Confidence is moderate and should be confirmed with objective workup.")
        if workup_items:
            uncertainty_factors.append("Confirmatory tests are still pending.")
            missing_data.extend([f"Pending: {item}" for item in workup_items[:4]])
        if standardized.get('safety_assessment', {}).get('issues'):
            uncertainty_factors.append("Safety review reported issues requiring clinician review.")

        diagnosis_evidence: List[Dict[str, Any]] = []
        feature_lower = [item.lower() for item in features]
        for index, diagnosis in enumerate(differentials):
            support = self._diagnosis_support_features(diagnosis, features, feature_lower)
            against: List[str] = []
            if index > 0:
                against.append("Lower-ranked than primary diagnosis on current evidence.")
            if index == 0 and workup_items:
                against.append("Primary diagnosis still needs confirmatory objective testing.")

            diagnosis_evidence.append(
                {
                    'rank': index + 1,
                    'diagnosis': diagnosis,
                    'supporting_evidence': support,
                    'against_evidence': against,
                    'missing_data': [f"Need: {item}" for item in workup_items[:2]],
                }
            )

        return {
            'confidence_breakdown': {
                'score': confidence_score,
                'percent': confidence_percent,
                'drivers': self._clean_strings(confidence_drivers, limit=6),
                'uncertainty_factors': self._clean_strings(uncertainty_factors, limit=6),
                'missing_data': self._clean_strings(missing_data, limit=6),
            },
            'diagnosis_evidence': diagnosis_evidence,
        }

    def _diagnosis_support_features(
        self,
        diagnosis: str,
        features: List[str],
        feature_lower: List[str],
    ) -> List[str]:
        diagnosis_lower = diagnosis.lower()

        diagnosis_feature_hints = {
            'pneumonia': ['fever', 'cough', 'dyspnea', 'chest pain'],
            'influenza': ['fever', 'body aches', 'headache', 'sore throat'],
            'tuberculosis': ['chronic cough', 'hemoptysis', 'weight loss', 'night sweats'],
            'depress': ['depressed mood', 'anhedonia', 'insomnia', 'suicidal ideation'],
            'mccune': ['precocious puberty', 'cafe-au-lait spots', 'fibrous dysplasia'],
            'urinary': ['dysuria', 'frequency', 'urgency', 'flank pain'],
            'asthma': ['dyspnea', 'wheezing', 'cough'],
        }

        expected_terms: List[str] = []
        for token, terms in diagnosis_feature_hints.items():
            if token in diagnosis_lower:
                expected_terms.extend(terms)

        supporting: List[str] = []
        for idx, item in enumerate(feature_lower):
            if len(supporting) >= 3:
                break
            if expected_terms and not any(term in item for term in expected_terms):
                continue
            supporting.append(features[idx])

        if not supporting:
            supporting = features[: min(3, len(features))]

        if not supporting:
            supporting = ['Limited explicit feature extraction; correlate with full clinical context.']

        return supporting

    def _fetch_feedback_hints(self, symptoms: str, clinical_notes: str) -> List[Dict[str, Any]]:
        try:
            from diagnosis.models import ClinicalFeedback
        except Exception:
            return []

        query_text = re.sub(r'\s+', ' ', f"{symptoms} {clinical_notes}".strip().lower())
        if not query_text:
            return []

        tokens = {
            token
            for token in re.findall(r'[a-z0-9]{4,}', query_text)
            if token not in {'with', 'without', 'history', 'patient', 'pain', 'days', 'week'}
        }
        if not tokens:
            return []

        recent_feedback = list(
            ClinicalFeedback.objects.all()
            .order_by('-created_at')[: self.feedback_hint_window]
        )
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for item in recent_feedback:
            reference_text = re.sub(
                r'\s+',
                ' ',
                f"{item.symptom_signature} {item.ai_primary_diagnosis} {item.doctor_final_diagnosis} {item.correction_summary}".lower(),
            )
            if not reference_text:
                continue
            reference_tokens = set(re.findall(r'[a-z0-9]{4,}', reference_text))
            if not reference_tokens:
                continue
            overlap = tokens.intersection(reference_tokens)
            if not overlap:
                continue

            score = len(overlap) / max(1, len(tokens))
            summary = (
                f"Past correction: AI '{item.ai_primary_diagnosis or 'n/a'}' -> "
                f"Doctor '{item.doctor_final_diagnosis or 'n/a'}'."
            )
            if item.correction_summary:
                summary = f"{summary} {item.correction_summary[:180]}"

            scored.append(
                (
                    score,
                    {
                        'summary': summary,
                        'score': round(score, 3),
                        'feedback_note': item.feedback_note[:180],
                    },
                )
            )

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [payload for _, payload in scored[: self.feedback_hint_limit]]

    def _append_feedback_hints_to_notes(self, clinical_notes: str, feedback_hints: List[Dict[str, Any]]) -> str:
        hint_lines = [item.get('summary', '').strip() for item in feedback_hints if item.get('summary')]
        if not hint_lines:
            return clinical_notes
        feedback_block = "Doctor feedback memory (use as calibration hints, not hard constraints):\n- " + "\n- ".join(
            hint_lines[:3]
        )
        if clinical_notes:
            return f"{clinical_notes}\n\n{feedback_block}"
        return feedback_block

    def _render_reasoning_text(self, standardized: Dict[str, Any]) -> str:
        lines: List[str] = []

        primary = standardized.get('primary_diagnosis', '')
        lines.append(f"PRIMARY DIAGNOSIS: {primary or 'Undifferentiated presentation'}")

        lines.append('DIFFERENTIAL DIAGNOSES:')
        differentials = standardized.get('differential_diagnoses', [])
        if differentials:
            for idx, term in enumerate(differentials[:5], 1):
                lines.append(f"{idx}. {term}")
        else:
            lines.append('- No high-confidence differential generated')

        lines.append(f"CONFIDENCE: {int(self._safe_confidence(standardized.get('confidence_score', 0)) * 100)}%")

        lines.append('RECOMMENDED WORKUP:')
        workup = standardized.get('recommended_workup', [])
        if workup:
            for item in workup[:6]:
                lines.append(f"- {item}")
        else:
            lines.append('- Additional data required before definitive workup')

        lines.append('MEDICATION RECOMMENDATIONS:')
        meds = standardized.get('medications', [])
        if meds:
            for med in meds[:5]:
                lines.append(
                    f"- {med.get('name', '')} | {med.get('dosage', '')} | {med.get('frequency', '')} | {med.get('duration', '')}"
                )
        else:
            lines.append('- No empiric medications recommended')

        safety = standardized.get('safety_assessment', {})
        if safety.get('issues'):
            lines.append('SAFETY NOTES:')
            for issue in safety.get('issues', [])[:4]:
                lines.append(f"- {issue}")

        summary = standardized.get('summary', '')
        if summary:
            lines.append('CLINICAL SUMMARY:')
            lines.append(summary)

        return '\n'.join(lines)

    def _tokenize_for_stream(self, text: str) -> List[str]:
        compact_text = str(text or '').strip()
        if not compact_text:
            return []

        tokens = re.findall(r'\S+\s*', compact_text)
        max_tokens = int(os.environ.get('HYBRID_STREAM_MAX_TOKENS', '260'))
        if len(tokens) > max_tokens:
            tokens = tokens[:max_tokens]
            tokens.append('...')
        return tokens

    def _safe_confidence(self, value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0.0
        return max(0.0, min(score, 0.99))

    def _looks_like_dosage(self, text: str) -> bool:
        value = str(text or '').strip().lower()
        if not value:
            return False
        dosage_pattern = r'\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu|units?|puffs?|tabs?|tablets?|capsules?|drops?)\b'
        route_or_form_pattern = r'\b(?:po|iv|im|sc|sq|inh|inhaled|topical|oral)\b'
        if re.search(dosage_pattern, value):
            return True
        if re.search(route_or_form_pattern, value) and re.search(r'\d', value):
            return True
        return False

    def _looks_like_frequency(self, text: str) -> bool:
        value = str(text or '').strip().lower()
        if not value:
            return False
        frequency_pattern = (
            r'\b(?:every|q\d+h|once|twice|three times|daily|weekly|hourly|prn|bid|tid|qid|'
            r'morning|night|bedtime|before|after)\b'
        )
        day_schedule_pattern = r'\bday\s*\d+\b|^\d+(?:\s*,\s*\d+)+$'
        if re.search(frequency_pattern, value):
            return True
        if re.search(day_schedule_pattern, value):
            return True
        return False

    def _normalize_medication_entry(self, med: Dict[str, str]) -> Dict[str, Any]:
        normalized = {
            'name': str(med.get('name', '')).strip(),
            'dosage': str(med.get('dosage', '')).strip(),
            'frequency': str(med.get('frequency', '')).strip(),
            'duration': str(med.get('duration', '')).strip(),
            'instructions': str(med.get('instructions', '')).strip(),
        }

        dosage_is_frequency = (
            self._looks_like_frequency(normalized['dosage']) and not self._looks_like_dosage(normalized['dosage'])
        )
        frequency_is_dosage = (
            self._looks_like_dosage(normalized['frequency']) and not self._looks_like_frequency(normalized['frequency'])
        )
        if dosage_is_frequency and frequency_is_dosage:
            normalized['dosage'], normalized['frequency'] = normalized['frequency'], normalized['dosage']

        if normalized['duration']:
            duration_has_time = re.search(
                r'\b(?:day|days|week|weeks|month|months|year|years|as needed|prn)\b',
                normalized['duration'].lower(),
            )
            if not duration_has_time and len(normalized['duration'].split()) >= 6:
                if normalized['instructions']:
                    normalized['instructions'] = f"{normalized['instructions']}; {normalized['duration']}"
                else:
                    normalized['instructions'] = normalized['duration']
                normalized['duration'] = 'Per clinical protocol'

        schedule = self._derive_schedule_from_frequency(normalized['frequency'])
        normalized.update(schedule)

        return normalized

    def _derive_schedule_from_frequency(self, frequency: str) -> Dict[str, Any]:
        value = str(frequency or '').strip().lower()
        schedule: Dict[str, Any] = {
            'schedule_type': 'free_text',
            'every_hours': None,
            'times_per_day': None,
            'take_morning': False,
            'take_noon': False,
            'take_evening': False,
            'take_bedtime': False,
            'take_with_breakfast': False,
            'take_with_lunch': False,
            'take_with_dinner': False,
        }
        if not value:
            return schedule

        hour_match = re.search(r'\b(?:every|q)\s*(\d{1,2})\s*(?:h|hr|hour|hours)\b', value)
        if not hour_match:
            hour_match = re.search(r'\bevery\s*(\d{1,2})\s*(?:hours|hour)\b', value)
        if hour_match:
            schedule['schedule_type'] = 'per_hour'
            schedule['every_hours'] = int(hour_match.group(1))
            return schedule

        per_day_match = re.search(r'\b(\d{1,2})\s*(?:x|times?)\s*(?:per\s*)?day\b', value)
        if per_day_match:
            schedule['schedule_type'] = 'per_day'
            schedule['times_per_day'] = int(per_day_match.group(1))
        elif re.search(r'\bqid\b', value) or 'four times daily' in value or 'four times a day' in value:
            schedule['schedule_type'] = 'per_day'
            schedule['times_per_day'] = 4
        elif re.search(r'\btid\b', value) or 'three times daily' in value or 'three times a day' in value:
            schedule['schedule_type'] = 'per_day'
            schedule['times_per_day'] = 3
        elif re.search(r'\bbid\b', value) or 'twice daily' in value or 'twice a day' in value:
            schedule['schedule_type'] = 'per_day'
            schedule['times_per_day'] = 2
        elif re.search(r'\bod\b', value) or 'once daily' in value or 'once a day' in value or 'daily' in value:
            schedule['schedule_type'] = 'per_day'
            schedule['times_per_day'] = 1

        if 'morning' in value or re.search(r'\bam\b', value):
            schedule['take_morning'] = True
        if 'noon' in value or 'afternoon' in value:
            schedule['take_noon'] = True
        if 'evening' in value or 'night' in value:
            schedule['take_evening'] = True
        if 'bedtime' in value or re.search(r'\bhs\b', value) or 'before sleep' in value:
            schedule['take_bedtime'] = True
        if 'breakfast' in value:
            schedule['take_with_breakfast'] = True
        if 'lunch' in value:
            schedule['take_with_lunch'] = True
        if 'dinner' in value or 'supper' in value:
            schedule['take_with_dinner'] = True

        if any(
            [
                schedule['take_morning'],
                schedule['take_noon'],
                schedule['take_evening'],
                schedule['take_bedtime'],
                schedule['take_with_breakfast'],
                schedule['take_with_lunch'],
                schedule['take_with_dinner'],
            ]
        ):
            schedule['schedule_type'] = 'specific_times'

        return schedule

    def _build_cache_key(self, symptoms: str, clinical_notes: str) -> str:
        normalized = re.sub(r'\s+', ' ', f"{symptoms}\n{clinical_notes}".strip().lower())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def _get_cached(self, key: str) -> Dict[str, Any]:
        cached = self._cache.get(key)
        if not cached:
            return {}

        if time.time() - cached.get('timestamp', 0) > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return {}

        return cached.get('payload', {})

    def _set_cached(self, key: str, payload: Dict[str, Any]) -> None:
        if len(self._cache) >= self.cache_max_items:
            oldest_key = min(self._cache.items(), key=lambda item: item[1].get('timestamp', 0))[0]
            self._cache.pop(oldest_key, None)

        self._cache[key] = {'timestamp': time.time(), 'payload': payload}

    def _clean_strings(self, values: Any, limit: int = 6) -> List[str]:
        if not isinstance(values, list):
            return []

        cleaned: List[str] = []
        seen = set()
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
            if len(cleaned) >= limit:
                break
        return cleaned

    def _diagnosis_key(self, value: str) -> str:
        normalized = re.sub(r'[^a-z0-9\s]+', ' ', str(value or '').lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def _matches_any_diagnosis(self, candidate: str, options: List[str]) -> bool:
        candidate_key = self._diagnosis_key(candidate)
        if not candidate_key:
            return False

        for option in options:
            option_key = self._diagnosis_key(option)
            if not option_key:
                continue
            if candidate_key == option_key or candidate_key in option_key or option_key in candidate_key:
                return True
        return False

    def _empty_standardized(self, error_text: str) -> Dict[str, Any]:
        return {
            'primary_diagnosis': '',
            'differential_diagnoses': [],
            'red_flags': [],
            'recommended_workup': [],
            'medications': [],
            'medication_safety': {'overall_risk': 'low', 'requires_review': False, 'alerts': [], 'per_medication': []},
            'confidence_score': 0.0,
            'safety_assessment': {'passed': False, 'issues': [error_text]},
            'validator_notes': 'analysis failed',
            'summary': '',
            'hallucination_flags': [],
        }

    def _empty_compatibility(self, error_text: str) -> Dict[str, Any]:
        return {
            'error': error_text,
            'confidence_score': 0.0,
            'suggested_diagnoses': [],
            'keywords': [],
            'interpretation': 'Analysis failed',
            'clinical_reasoning': error_text,
            'raw_clinical_reasoning': error_text,
            'summary': '',
            'recommendations': [],
            'medications': [],
            'medication_safety': {'overall_risk': 'low', 'requires_review': False, 'alerts': [], 'per_medication': []},
            'explainability': {
                'confidence_breakdown': {
                    'score': 0.0,
                    'percent': 0,
                    'drivers': [],
                    'uncertainty_factors': [error_text],
                    'missing_data': [],
                },
                'diagnosis_evidence': [],
            },
            'feedback_loop_info': {'used_hints': False, 'hint_count': 0, 'hints': []},
            'red_flag_analysis': {'has_red_flags': False, 'urgency_level': 'UNKNOWN', 'detected_flags': []},
            'validation_warning': error_text,
            'validator_info': {
                'validator_status': 'error',
                'safety_passed': False,
                'issues': [error_text],
                'hallucination_flags': [],
            },
        }


hybrid_orchestrator = HybridDiagnosisOrchestrator()
