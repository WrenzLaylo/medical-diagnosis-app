import re
from typing import Any, Dict, List, Set, Tuple


class MedicationSafetyEngine:
    """Rule-based medication safety checks for clinician review support."""

    def assess(self, medications: List[Dict[str, Any]], context_text: str = '') -> Dict[str, Any]:
        meds = self._normalize_medications(medications)
        profile = self._detect_profile(context_text)

        alerts: List[Dict[str, str]] = []
        per_medication: List[Dict[str, Any]] = []

        for med in meds:
            med_alerts = self._evaluate_medication_rules(med, profile)
            per_medication.append(
                {
                    'medication_name': med['display_name'],
                    'risk_level': self._risk_from_alerts(med_alerts),
                    'alerts': med_alerts,
                }
            )
            alerts.extend(med_alerts)

        alerts.extend(self._evaluate_interactions(meds))

        deduped_alerts = self._dedupe_alerts(alerts)
        risk_level = self._risk_from_alerts(deduped_alerts)

        return {
            'overall_risk': risk_level,
            'requires_review': risk_level in ['moderate', 'high'],
            'alerts': deduped_alerts[:10],
            'per_medication': per_medication[:8],
            'detected_profile': profile,
        }

    def _normalize_medications(self, medications: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        normalized: List[Dict[str, str]] = []
        for item in medications[:12]:
            if not isinstance(item, dict):
                continue
            raw_name = str(
                item.get('medication_name')
                or item.get('name')
                or ''
            ).strip()
            if not raw_name:
                continue
            normalized.append(
                {
                    'display_name': raw_name,
                    'name': raw_name.lower(),
                    'dosage': str(item.get('dosage', '')).strip().lower(),
                    'frequency': str(item.get('frequency', '')).strip().lower(),
                    'duration': str(item.get('duration', '')).strip().lower(),
                }
            )
        return normalized

    def _detect_profile(self, context_text: str) -> Dict[str, Any]:
        value = str(context_text or '').lower()
        age_years = self._extract_age(value)

        allergies: Set[str] = set()
        if re.search(r'\b(penicillin allergy|allergic to penicillin|pcn allergy|amoxicillin allergy)\b', value):
            allergies.add('penicillin')
        if re.search(r'\b(sulfa allergy|allergic to sulfa|sulfamethoxazole allergy)\b', value):
            allergies.add('sulfa')
        if re.search(r'\b(aspirin allergy|nsaid allergy|allergic to ibuprofen)\b', value):
            allergies.add('nsaid')

        renal_impairment = bool(
            re.search(
                r'\b(ckd|chronic kidney disease|renal failure|kidney failure|dialysis|egfr\s*<?\s*30)\b',
                value,
            )
        )
        hepatic_impairment = bool(
            re.search(r'\b(cirrhosis|liver failure|hepatic impairment|chronic hepatitis)\b', value)
        )
        pregnant = bool(re.search(r'\b(pregnant|pregnancy|gestation|positive pregnancy test)\b', value))
        gi_bleed_risk = bool(
            re.search(r'\b(peptic ulcer|gi bleed|gastrointestinal bleed|hematemesis|melena)\b', value)
        )
        asthma = bool(re.search(r'\b(asthma|bronchospasm|reactive airway)\b', value))

        return {
            'allergies': sorted(allergies),
            'renal_impairment': renal_impairment,
            'hepatic_impairment': hepatic_impairment,
            'pregnant': pregnant,
            'gi_bleed_risk': gi_bleed_risk,
            'asthma': asthma,
            'age_years': age_years,
        }

    def _extract_age(self, text: str) -> int:
        patterns = [
            r'\b(\d{1,2})\s*(?:years?\s*old|year-old|y/o)\b',
            r'\bage\s*[:=]?\s*(\d{1,2})\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    return 0
        return 0

    def _evaluate_medication_rules(self, med: Dict[str, str], profile: Dict[str, Any]) -> List[Dict[str, str]]:
        name = med['name']
        alerts: List[Dict[str, str]] = []

        if any(token in name for token in ['amoxicillin', 'ampicillin', 'augmentin', 'penicillin']) and 'penicillin' in profile['allergies']:
            alerts.append(
                self._alert(
                    severity='high',
                    medication=med['display_name'],
                    code='allergy_penicillin',
                    issue='Possible penicillin-class allergy conflict.',
                    recommendation='Verify allergy details and avoid beta-lactam unless cleared by clinician/allergy history.',
                )
            )

        if any(token in name for token in ['ibuprofen', 'naproxen', 'diclofenac', 'ketorolac']):
            if profile['renal_impairment']:
                alerts.append(
                    self._alert(
                        severity='high',
                        medication=med['display_name'],
                        code='nsaid_renal_risk',
                        issue='NSAID may worsen renal impairment.',
                        recommendation='Prefer non-NSAID alternatives and monitor renal function.',
                    )
                )
            if profile['gi_bleed_risk']:
                alerts.append(
                    self._alert(
                        severity='high',
                        medication=med['display_name'],
                        code='nsaid_gi_bleed_risk',
                        issue='NSAID increases gastrointestinal bleeding risk.',
                        recommendation='Avoid or co-manage with gastroprotection if clinically necessary.',
                    )
                )
            if profile['pregnant']:
                alerts.append(
                    self._alert(
                        severity='moderate',
                        medication=med['display_name'],
                        code='nsaid_pregnancy',
                        issue='NSAID caution in pregnancy.',
                        recommendation='Review trimester-specific risk and consider safer alternatives.',
                    )
                )

        if any(token in name for token in ['lisinopril', 'enalapril', 'losartan', 'valsartan']) and profile['pregnant']:
            alerts.append(
                self._alert(
                    severity='high',
                    medication=med['display_name'],
                    code='pregnancy_raas',
                    issue='RAAS blockers are generally contraindicated in pregnancy.',
                    recommendation='Stop/avoid and select pregnancy-safe antihypertensive therapy.',
                )
            )

        if any(token in name for token in ['atorvastatin', 'simvastatin', 'rosuvastatin']) and profile['pregnant']:
            alerts.append(
                self._alert(
                    severity='high',
                    medication=med['display_name'],
                    code='pregnancy_statin',
                    issue='Statin exposure should be avoided in pregnancy.',
                    recommendation='Hold statin and reassess lipid management postpartum.',
                )
            )

        if 'metformin' in name and profile['renal_impairment']:
            alerts.append(
                self._alert(
                    severity='high',
                    medication=med['display_name'],
                    code='metformin_renal_risk',
                    issue='Metformin may be unsafe with severe renal impairment.',
                    recommendation='Confirm eGFR and adjust/avoid per renal dosing guidance.',
                )
            )

        if 'nitrofurantoin' in name and profile['renal_impairment']:
            alerts.append(
                self._alert(
                    severity='moderate',
                    medication=med['display_name'],
                    code='nitrofurantoin_renal',
                    issue='Nitrofurantoin efficacy/safety may be reduced in renal impairment.',
                    recommendation='Review renal function and consider alternative antibiotic if needed.',
                )
            )

        if 'aspirin' in name and profile.get('age_years', 0) and profile['age_years'] < 18:
            alerts.append(
                self._alert(
                    severity='moderate',
                    medication=med['display_name'],
                    code='aspirin_pediatric',
                    issue='Aspirin in pediatric patients may carry Reye syndrome risk.',
                    recommendation='Avoid unless specifically indicated by specialist guidance.',
                )
            )

        if not med['dosage']:
            alerts.append(
                self._alert(
                    severity='moderate',
                    medication=med['display_name'],
                    code='missing_dosage',
                    issue='Dosage is missing.',
                    recommendation='Add an explicit dose before finalizing prescription.',
                )
            )
        if not med['frequency']:
            alerts.append(
                self._alert(
                    severity='moderate',
                    medication=med['display_name'],
                    code='missing_frequency',
                    issue='Frequency is missing.',
                    recommendation='Add schedule/frequency before finalizing prescription.',
                )
            )
        if not med['duration']:
            alerts.append(
                self._alert(
                    severity='low',
                    medication=med['display_name'],
                    code='missing_duration',
                    issue='Duration is missing.',
                    recommendation='Document intended treatment duration or review interval.',
                )
            )

        return alerts

    def _evaluate_interactions(self, meds: List[Dict[str, str]]) -> List[Dict[str, str]]:
        names = [med['name'] for med in meds]
        alerts: List[Dict[str, str]] = []

        def has_any(tokens: List[str]) -> bool:
            return any(any(token in med_name for token in tokens) for med_name in names)

        if has_any(['warfarin']) and has_any(['ibuprofen', 'naproxen', 'diclofenac', 'ketorolac']):
            alerts.append(
                self._alert(
                    severity='high',
                    medication='Medication combination',
                    code='interaction_warfarin_nsaid',
                    issue='Warfarin + NSAID combination detected.',
                    recommendation='High bleed risk; avoid combination or intensify monitoring.',
                )
            )

        if has_any(['warfarin']) and has_any(['metronidazole', 'trimethoprim', 'sulfamethoxazole']):
            alerts.append(
                self._alert(
                    severity='moderate',
                    medication='Medication combination',
                    code='interaction_warfarin_antibiotic',
                    issue='Warfarin with interacting antibiotic detected.',
                    recommendation='Monitor INR closely and adjust anticoagulation as needed.',
                )
            )

        return alerts

    def _alert(
        self,
        severity: str,
        medication: str,
        code: str,
        issue: str,
        recommendation: str,
    ) -> Dict[str, str]:
        return {
            'severity': severity,
            'medication': medication,
            'code': code,
            'issue': issue,
            'recommendation': recommendation,
        }

    def _risk_from_alerts(self, alerts: List[Dict[str, str]]) -> str:
        severities = {str(item.get('severity', '')).lower() for item in alerts}
        if 'high' in severities:
            return 'high'
        if 'moderate' in severities:
            return 'moderate'
        return 'low'

    def _dedupe_alerts(self, alerts: List[Dict[str, str]]) -> List[Dict[str, str]]:
        deduped: List[Dict[str, str]] = []
        seen: Set[Tuple[str, str, str]] = set()
        for alert in alerts:
            key = (
                str(alert.get('code', '')).strip().lower(),
                str(alert.get('medication', '')).strip().lower(),
                str(alert.get('issue', '')).strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(alert)
        return deduped
