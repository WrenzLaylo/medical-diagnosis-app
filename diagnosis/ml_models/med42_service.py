"""
Med42-v3 Clinical LLM Service - Production-Ready with Red Flag Detection

Major Improvements:
- RED FLAG DETECTION: Life-threatening symptoms trigger urgent workup alerts
- SYMPTOM PATTERN VALIDATION: Prevents keyword-only matching errors
- CLINICAL DECISION RULES: Structured reasoning for common presentations
- MEDICATION SAFETY: Evidence-based prescribing with contraindication checks
- DIFFERENTIAL RANKING: Proper Bayesian likelihood scoring
"""

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()

import os
import re
from typing import Dict, List, Any, Tuple
from huggingface_hub import InferenceClient


class Med42ServiceCloud:
    def __init__(self, model_size="8B", api_token=None):
        """Initialize Med42-v3 with enhanced safety and clinical reasoning"""
        self.model_size = model_size
        
        # Get API token
        self.api_token = api_token or os.environ.get('HF_TOKEN') or os.environ.get('HUGGINGFACE_API_TOKEN')
        
        if not self.api_token:
            raise ValueError("HF_TOKEN environment variable not set")
        
        # Initialize client
        self.client = InferenceClient(api_key=self.api_token)
        self.model_name = f"m42-health/Llama3-Med42-{model_size}:featherless-ai"
        
        # Enhanced system prompt with strict safety rules
        self.system_prompt = self._build_enhanced_system_prompt()
        
        # Initialize clinical decision rules
        self.red_flag_patterns = self._initialize_red_flags()
        self.symptom_clusters = self._initialize_symptom_clusters()
        self.medication_protocols = self._initialize_medication_protocols()
        
        print(f"[OK] Med42-v3-{self.model_size} Production Service Ready")
        print("  [OK] Red flag detection enabled")
        print("  [OK] Symptom pattern validation enabled")
        print("  [OK] Clinical decision rules loaded")
    
    def _build_enhanced_system_prompt(self) -> str:
        """Build concise, safety-focused clinical reasoning prompt"""
        return """You are Med42-v3 clinical decision support for licensed clinicians.

Core behavior:
- Prioritize patient safety and life-threatening causes first.
- Match diagnoses to the full symptom pattern, not isolated keywords.
- Use evidence hierarchy: objective findings > symptoms > history.
- Avoid benign labels when red flags are present.
- Calibrate confidence honestly; uncertainty should lower confidence.
- Recommend medications only when empiric treatment is reasonably safe.

Before writing your answer, silently:
1) list key positive and negative findings,
2) generate multiple candidate diagnoses,
3) rank by likelihood x severity.

Output format (use these exact section headers):
**PRIMARY DIAGNOSIS**: one diagnosis
**WHY THIS FITS**
- concise evidence bullets
**DIFFERENTIAL DIAGNOSES**
1. diagnosis | likelihood | key for/against
**CONFIDENCE**: percent + one-line rationale
**RECOMMENDED WORKUP**
1. urgent/high-yield tests first
**MEDICATION RECOMMENDATIONS**
- Medication | Dose | Frequency | Duration | Purpose | Safety note
- If unsafe/uncertain: "No empiric medications until further workup"
**CLINICAL SUMMARY**
2-4 lines with urgency and next step

Constraints:
- Keep response concise and doctor-readable.
- Prefer short bullets over long paragraphs.
- Max ~320 words."""

    def _initialize_red_flags(self) -> Dict[str, Dict]:
        """Initialize red flag symptom patterns"""
        return {
            'hemoptysis': {
                'keywords': ['coughing blood', 'cough blood', 'hemoptysis', 'blood in sputum', 'bloody cough'],
                'severity': 'URGENT',
                'ddx': ['Pulmonary TB', 'Lung cancer', 'Pulmonary embolism', 'Bronchiectasis', 'Vasculitis'],
                'workup': ['Chest X-ray', 'CBC', 'Sputum culture/AFB', 'CT chest', 'Coagulation studies']
            },
            'epistaxis_prolonged': {
                'keywords': ['nose bleed', 'nosebleed', 'epistaxis', 'bleeding nose'],
                'duration_days': 7,
                'severity': 'HIGH',
                'ddx': ['Thrombocytopenia', 'Coagulopathy', 'Hypertension', 'Nasal trauma', 'Leukemia'],
                'workup': ['CBC with platelets', 'PT/PTT/INR', 'Blood pressure', 'Nasal exam']
            },
            'chest_pain_dyspnea': {
                'keywords': ['chest pain', 'shortness of breath', 'dyspnea', 'difficulty breathing'],
                'severity': 'URGENT',
                'ddx': ['Acute coronary syndrome', 'Pulmonary embolism', 'Pneumothorax', 'Aortic dissection'],
                'workup': ['ECG', 'Troponin', 'Chest X-ray', 'D-dimer', 'CT angiography']
            },
            'altered_mental_status': {
                'keywords': ['confused', 'disoriented', 'altered mental', 'consciousness'],
                'severity': 'URGENT',
                'ddx': ['Stroke', 'Hypoglycemia', 'Sepsis', 'Metabolic encephalopathy', 'Meningitis'],
                'workup': ['Blood glucose', 'Head CT', 'Metabolic panel', 'Blood cultures', 'Lumbar puncture']
            },
            'severe_headache': {
                'keywords': ['worst headache', 'thunderclap headache', 'severe headache', 'neck stiff'],
                'severity': 'URGENT',
                'ddx': ['Subarachnoid hemorrhage', 'Meningitis', 'Mass lesion', 'Hypertensive crisis'],
                'workup': ['Head CT', 'Lumbar puncture', 'Blood pressure', 'Fundoscopy']
            },
            'multiple_bleeding_sites': {
                'combined_keywords': [
                    ['coughing blood', 'nose bleed'],
                    ['bleeding gums', 'bruising'],
                    ['blood in stool', 'nose bleed']
                ],
                'severity': 'URGENT',
                'ddx': ['Disseminated intravascular coagulation', 'Thrombocytopenia', 'Leukemia', 'Von Willebrand disease'],
                'workup': ['CBC with differential', 'PT/PTT/INR', 'Fibrinogen', 'Peripheral smear', 'Bone marrow biopsy']
            },
            'suicidal_ideation': {
                'keywords': [
                    'suicidal ideation',
                    'suicidal thoughts',
                    'thoughts of death',
                    'recurrent thoughts of death',
                    'self harm',
                    'self-harm',
                    'wants to die',
                ],
                'severity': 'URGENT',
                'ddx': [
                    'Major depressive episode',
                    'Bipolar depression',
                    'Substance-induced mood disorder',
                    'Psychotic disorder',
                ],
                'workup': [
                    'Immediate suicide risk assessment',
                    'Urgent psychiatric evaluation',
                    'Safety planning and close monitoring',
                    'Consider emergency referral/hospitalization',
                ],
            }
        }
    
    def _initialize_symptom_clusters(self) -> Dict[str, Dict]:
        """Define expected symptom patterns for common diagnoses"""
        return {
            'angioedema': {
                'required': ['swelling'],
                'typical_locations': ['lips', 'tongue', 'face', 'throat', 'airway'],
                'may_have': ['hives', 'urticaria', 'pruritus'],
                'should_not_have': ['hemoptysis', 'epistaxis', 'chronic_cough'],
                'timeframe': 'acute (minutes to hours)'
            },
            'pulmonary_tb': {
                'required': ['chronic_cough'],
                'duration': '>2-3 weeks',
                'typical': ['hemoptysis', 'night_sweats', 'weight_loss', 'fever'],
                'may_have': ['fatigue', 'chest_pain', 'dyspnea'],
                'risk_factors': ['endemic area', 'immunocompromised', 'recent exposure']
            },
            'tuberculosis': {
                'required': ['chronic_cough'],
                'duration': '>2-3 weeks',
                'typical': ['hemoptysis', 'night_sweats', 'weight_loss', 'fever'],
                'may_have': ['fatigue', 'chest_pain', 'dyspnea']
            },
            'bleeding_disorder': {
                'required': ['abnormal_bleeding'],
                'patterns': ['multiple sites', 'prolonged', 'spontaneous'],
                'typical': ['epistaxis', 'gingival bleeding', 'bruising', 'petechiae'],
                'may_have': ['menorrhagia', 'hematuria', 'hemoptysis']
            },
            'thrombocytopenia': {
                'required': ['bleeding'],
                'typical': ['petechiae', 'bruising', 'epistaxis', 'gingival_bleeding'],
                'may_have': ['hemoptysis', 'gi_bleeding'],
                'labs_required': ['low platelet count']
            },
            'celiac_disease': {
                'required': ['gi_symptoms'],
                'typical': ['chronic_diarrhea', 'bloating', 'weight_loss', 'malabsorption'],
                'labs_required': ['positive tissue transglutaminase IgA', 'villous atrophy on biopsy'],
                'may_have': ['anemia', 'vitamin_deficiencies', 'dermatitis_herpetiformis'],
                'should_not_diagnose_if': ['normal labs', 'no gi symptoms']
            },
            'celiac': {
                'required': ['gi_symptoms'],
                'typical': ['diarrhea', 'bloating', 'weight_loss'],
                'labs_required': ['positive serology or biopsy'],
                'should_not_diagnose_if': ['normal labs']
            },
            'pneumonia': {
                'required': ['cough'],
                'typical': ['fever', 'dyspnea', 'chest_pain', 'productive_sputum'],
                'may_have': ['pleuritic_pain', 'tachypnea', 'crackles'],
                'should_not_have': ['chronic_cough_alone']
            },
            'asthma': {
                'required': ['dyspnea', 'wheezing'],
                'typical': ['cough', 'chest_tightness', 'nocturnal_symptoms'],
                'may_have': ['allergies', 'eczema', 'family_history'],
                'should_not_have': ['hemoptysis', 'chronic_productive_cough']
            },
            'copd': {
                'required': ['chronic_dyspnea'],
                'typical': ['chronic_cough', 'sputum_production', 'smoking_history'],
                'may_have': ['wheezing', 'barrel_chest', 'weight_loss'],
                'should_not_have': ['acute_onset_only']
            },
            'acute_copd_exacerbation': {
                'required': ['dyspnea', 'cough'],
                'typical': ['sputum_production', 'wheezing', 'hypoxemia'],
                'may_have': ['fever', 'crackles', 'fatigue'],
                'should_not_have': []
            },
            'gerd': {
                'required': ['heartburn', 'regurgitation'],
                'typical': ['chest_discomfort', 'dysphagia', 'worse_lying_down'],
                'may_have': ['chronic_cough', 'hoarseness'],
                'should_not_have': ['hemoptysis', 'weight_loss', 'dysphagia_solids']
            },
            'ibs': {
                'required': ['abdominal_pain', 'bowel_habit_change'],
                'typical': ['bloating', 'diarrhea_or_constipation'],
                'should_not_have': ['weight_loss', 'bleeding', 'anemia', 'fever'],
                'labs_required': ['normal labs to exclude organic disease']
            },
            'acute_coronary_syndrome': {
                'required': ['chest_pain'],
                'typical': ['chest_pressure', 'radiation', 'dyspnea', 'diaphoresis'],
                'may_have': ['nausea', 'vomiting', 'palpitations'],
                'should_not_have': ['pleuritic_pain', 'positional_relief']
            },
            'pulmonary_embolism': {
                'required': ['dyspnea'],
                'typical': ['chest_pain', 'tachycardia', 'tachypnea'],
                'may_have': ['hemoptysis', 'leg_swelling', 'risk_factors'],
                'should_not_have': ['chronic_gradual_onset']
            },
            'anemia': {
                'required': ['fatigue'],
                'typical': ['weakness', 'pallor', 'dyspnea_on_exertion'],
                'may_have': ['dizziness', 'palpitations', 'headache'],
                'labs_required': ['low hemoglobin/hematocrit']
            },
            'hypothyroidism': {
                'required': ['fatigue', 'weight_gain'],
                'typical': ['cold_intolerance', 'constipation', 'dry_skin'],
                'may_have': ['hair_loss', 'bradycardia', 'depression'],
                'labs_required': ['elevated TSH']
            },
            'hyperthyroidism': {
                'required': ['weight_loss'],
                'typical': ['palpitations', 'heat_intolerance', 'tremor', 'anxiety'],
                'may_have': ['diarrhea', 'tachycardia', 'goiter'],
                'labs_required': ['low TSH, elevated T4/T3']
            },
            'diabetes': {
                'required': ['hyperglycemia'],
                'typical': ['polyuria', 'polydipsia', 'polyphagia'],
                'may_have': ['weight_loss', 'fatigue', 'blurred_vision'],
                'labs_required': ['elevated glucose or HbA1c']
            },
            'uncontrolled_type_2_diabetes_mellitus': {
                'required': ['hyperglycemia'],
                'typical': ['polyuria', 'polydipsia', 'elevated_hba1c'],
                'may_have': ['fatigue', 'poor_medication_adherence'],
                'should_not_have': []
            },
            'hypertension_with_renal_impairment': {
                'required': ['hypertension'],
                'typical': ['renal_impairment', 'elevated_creatinine', 'reduced_egfr'],
                'may_have': ['diabetes', 'palpitations', 'dyspnea_on_exertion'],
                'should_not_have': []
            },
            'acute_gout_flare': {
                'required': ['acute_joint_pain'],
                'typical': ['great_toe_pain', 'mcp1_swelling', 'erythema', 'hyperuricemia'],
                'may_have': ['joint_tenderness', 'warm_joint', 'fatigue'],
                'should_not_have': []
            },
            'uti': {
                'required': ['dysuria'],
                'typical': ['frequency', 'urgency', 'suprapubic_pain'],
                'may_have': ['hematuria', 'fever', 'flank_pain'],
                'should_not_have': ['chronic_symptoms_without_infection']
            },
            'allergic_rhinitis': {
                'required': ['nasal_symptoms'],
                'typical': ['sneezing', 'rhinorrhea', 'nasal_congestion', 'itching'],
                'may_have': ['conjunctivitis', 'post_nasal_drip'],
                'should_not_have': ['hemoptysis', 'chronic_epistaxis', 'systemic_symptoms']
            },
            'influenza_like_illness': {
                'required': ['fever', 'cough'],
                'typical': ['body_aches', 'headache', 'sore_throat', 'rhinorrhea'],
                'may_have': ['fatigue', 'chills'],
                'should_not_have': ['hemoptysis', 'severe_abdominal_pain']
            },
            'viral_upper_respiratory_infection': {
                'required': ['cough'],
                'typical': ['rhinorrhea', 'nasal_congestion', 'sore_throat'],
                'may_have': ['fever', 'body_aches', 'headache'],
                'should_not_have': ['hemoptysis', 'chest_pain_severe', 'dyspnea_severe']
            },
            'major_depressive_episode': {
                'required': ['depressed_mood'],
                'typical': [
                    'anhedonia',
                    'insomnia',
                    'fatigue',
                    'worthlessness',
                    'poor_concentration',
                    'psychomotor_retardation',
                    'suicidal_ideation',
                ],
                'may_have': ['weight_loss', 'guilt', 'hopelessness'],
                'should_not_have': ['manic_symptoms'],
            },
            'mccune_albright_syndrome': {
                'required': ['precocious_puberty', 'cafe_au_lait_spots', 'fibrous_dysplasia'],
                'typical': ['endocrine_hyperfunction', 'bone_pain', 'fractures'],
                'may_have': ['vaginal_bleeding', 'testicular_enlargement', 'thyrotoxicosis'],
                'should_not_have': [],
            },
            'peripheral_precocious_puberty': {
                'required': ['precocious_puberty'],
                'typical': ['advanced_bone_age', 'vaginal_bleeding', 'testicular_enlargement'],
                'may_have': ['ovarian_cyst', 'adrenal_source'],
                'should_not_have': [],
            },
            'central_precocious_puberty': {
                'required': ['precocious_puberty'],
                'typical': ['advanced_bone_age', 'growth_acceleration'],
                'may_have': ['headache', 'visual_changes'],
                'should_not_have': [],
            },
            'neurofibromatosis_type_1': {
                'required': ['cafe_au_lait_spots'],
                'typical': ['axillary_freckling', 'neurofibromas', 'lisch_nodules'],
                'may_have': ['optic_pathway_glioma', 'learning_difficulties'],
                'should_not_have': [],
            },
            'fibrous_dysplasia': {
                'required': ['fibrous_dysplasia'],
                'typical': ['bone_pain', 'fractures', 'bone_deformity'],
                'may_have': ['limp', 'facial_asymmetry'],
                'should_not_have': [],
            },
        }

    def _initialize_medication_protocols(self) -> Dict[str, List[Dict[str, str]]]:
        """Conservative fallback medication plans for common outpatient diagnoses"""
        return {
            'pneumonia': [
                {
                    'medication_name': 'Amoxicillin-Clavulanate',
                    'dosage': '875/125 mg',
                    'frequency': 'PO every 12 hours',
                    'duration': '5-7 days',
                    'instructions': 'Typical adult CAP regimen; verify allergies, renal dose, and local resistance.'
                }
            ],
            'asthma': [
                {
                    'medication_name': 'Albuterol inhaler',
                    'dosage': '90 mcg/puff',
                    'frequency': '1-2 puffs every 4-6 hours PRN',
                    'duration': 'As needed',
                    'instructions': 'Rescue therapy; escalate care if persistent dyspnea, hypoxia, or poor response.'
                }
            ],
            'copd': [
                {
                    'medication_name': 'Albuterol inhaler',
                    'dosage': '90 mcg/puff',
                    'frequency': '1-2 puffs every 4-6 hours PRN',
                    'duration': 'As needed',
                    'instructions': 'Symptom relief; assess oxygenation and exacerbation severity.'
                }
            ],
            'acute copd exacerbation': [
                {
                    'medication_name': 'Albuterol + Ipratropium',
                    'dosage': '2.5 mg/0.5 mg nebulized',
                    'frequency': 'Every 4-6 hours',
                    'duration': '3-5 days',
                    'instructions': 'Short-acting bronchodilator combination for acute airflow limitation.'
                },
                {
                    'medication_name': 'Prednisone',
                    'dosage': '40 mg',
                    'frequency': 'PO once daily',
                    'duration': '5 days',
                    'instructions': 'Short oral steroid burst if no contraindication; monitor glucose closely in diabetes.'
                },
                {
                    'medication_name': 'Acetaminophen',
                    'dosage': '500 mg',
                    'frequency': 'PO every 6-8 hours PRN',
                    'duration': 'Up to 3 days',
                    'instructions': 'Use for fever/pain when NSAIDs are not preferred or contraindicated.'
                },
            ],
            'gerd': [
                {
                    'medication_name': 'Omeprazole',
                    'dosage': '20 mg',
                    'frequency': 'PO once daily before breakfast',
                    'duration': '4-8 weeks',
                    'instructions': 'Trial for reflux symptoms; reassess alarm features (dysphagia, GI bleeding, weight loss).'
                }
            ],
            'uti': [
                {
                    'medication_name': 'Nitrofurantoin monohydrate/macrocrystals',
                    'dosage': '100 mg',
                    'frequency': 'PO every 12 hours',
                    'duration': '5 days',
                    'instructions': 'For uncomplicated cystitis when clinically appropriate; avoid if concern for pyelonephritis.'
                }
            ],
            'allergic rhinitis': [
                {
                    'medication_name': 'Cetirizine',
                    'dosage': '10 mg',
                    'frequency': 'PO once daily',
                    'duration': 'As needed',
                    'instructions': 'Non-sedating antihistamine for allergic symptoms.'
                }
            ],
            'influenza-like illness': [
                {
                    'medication_name': 'Acetaminophen',
                    'dosage': '500 mg',
                    'frequency': 'PO every 6-8 hours PRN',
                    'duration': '3 days',
                    'instructions': 'Supportive care for fever and body aches; avoid duplicate acetaminophen products.'
                }
            ],
            'viral upper respiratory infection': [
                {
                    'medication_name': 'Cetirizine',
                    'dosage': '10 mg',
                    'frequency': 'PO once daily PRN',
                    'duration': '3-5 days',
                    'instructions': 'Symptomatic relief for runny nose and sneezing; re-evaluate if symptoms worsen.'
                }
            ]
        }

    def _normalize_condition_name(self, condition: str) -> str:
        """Convert internal condition keys to clinician-friendly names"""
        aliases = {
            'pulmonary_tb': 'Pulmonary TB',
            'tuberculosis': 'Pulmonary TB',
            'acute_coronary_syndrome': 'Acute coronary syndrome',
            'pulmonary_embolism': 'Pulmonary embolism',
            'bleeding_disorder': 'Bleeding disorder',
            'celiac_disease': 'Celiac disease',
            'celiac': 'Celiac disease',
            'uti': 'Urinary tract infection',
            'ibs': 'Irritable bowel syndrome',
            'gerd': 'Gastroesophageal reflux disease',
            'copd': 'COPD',
            'acute_copd_exacerbation': 'Acute COPD exacerbation',
            'influenza_like_illness': 'Influenza-like illness',
            'viral_upper_respiratory_infection': 'Viral upper respiratory infection',
            'major_depressive_episode': 'Major depressive episode',
            'uncontrolled_type_2_diabetes_mellitus': 'Uncontrolled type 2 diabetes mellitus',
            'hypertension_with_renal_impairment': 'Hypertension with renal impairment',
            'acute_gout_flare': 'Acute gout flare',
            'mccune_albright_syndrome': 'McCune-Albright syndrome',
            'peripheral_precocious_puberty': 'Peripheral precocious puberty',
            'central_precocious_puberty': 'Central precocious puberty',
            'neurofibromatosis_type_1': 'Neurofibromatosis type 1 (NF1)',
            'fibrous_dysplasia': 'Fibrous dysplasia',
        }
        if condition in aliases:
            return aliases[condition]
        return condition.replace('_', ' ').strip().title()

    def _canonical_diagnosis(self, diagnosis: str) -> str:
        """Normalize diagnosis string for duplicate checks"""
        normalized = diagnosis.lower().strip()
        normalized = normalized.replace('tuberculosis', 'tb')
        normalized = normalized.replace('pulmonary tuberculosis', 'pulmonary tb')
        normalized = normalized.replace('mccune albright', 'mccune albright syndrome')
        normalized = normalized.replace('mccune-albright', 'mccune albright syndrome')
        normalized = normalized.replace('type ii diabetes', 'type 2 diabetes')
        normalized = normalized.replace('t2dm', 'type 2 diabetes')
        normalized = normalized.replace('ckd', 'chronic kidney disease')
        normalized = normalized.replace('renal dysfunction', 'renal impairment')
        normalized = normalized.replace('acute exacerbation of copd', 'acute copd exacerbation')
        normalized = normalized.replace('aecopd', 'acute copd exacerbation')
        normalized = normalized.replace('nf1', 'neurofibromatosis type 1')
        normalized = normalized.replace('familial adenomatous polyposis', 'fap')
        normalized = normalized.replace('podagra', 'gout')
        normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def _diagnoses_match(self, left: str, right: str) -> bool:
        """Loose matching for diagnosis equivalence"""
        l = self._canonical_diagnosis(left)
        r = self._canonical_diagnosis(right)
        if not l or not r:
            return False
        return l == r or l in r or r in l

    def _feature_present(self, feature: str, text: str) -> bool:
        """Check whether a clinical feature is present with negation handling"""
        phrase = feature.replace('_', ' ').lower().strip()
        checks = [phrase]
        checks.extend(self._get_symptom_variations(phrase))
        # Limit variation fan-out to preserve runtime determinism.
        for term in list(dict.fromkeys(checks))[:10]:
            if self._is_present_and_not_negated(term, text):
                return True
        return False

    def _normalize_multilingual_symptoms(self, text: str) -> str:
        """Normalize common Filipino symptom phrases to clinically standard English."""
        normalized = re.sub(r'\s+', ' ', str(text or '').strip())
        if not normalized:
            return ''

        replacements = [
            (r'\bsakit\s+ng\s+katawan\b', 'body aches'),
            (r'\bpananakit\s+ng\s+katawan\b', 'body aches'),
            (r'\bmasakit\s+ang\s+lalamunan\b', 'sore throat'),
            (r'\bsumasakit\s+ang\s+lalamunan\b', 'sore throat'),
            (r'\bhirap\s+huminga\b', 'shortness of breath'),
            (r'\bnahihilo\b', 'dizziness'),
            (r'\binuubo\b', 'cough'),
            (r'\bubo\b', 'cough'),
            (r'\bsipon\b', 'runny nose'),
            (r'\blagnat\b', 'fever'),
            (r'\bnilalagnat\b', 'fever'),
            (r'\btrangkaso\b', 'flu-like illness'),
            (r'\bmasakit\s+ulo\b', 'headache'),
        ]

        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        return normalized

    def _build_pre_diagnostic_hypotheses(
        self, symptoms_text: str, clinical_notes: str, red_flag_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Heuristic pre-ranking before LLM call to improve differential quality"""
        combined_text = f"{symptoms_text} {clinical_notes}".lower()
        candidates = []

        for condition, pattern in self.symptom_clusters.items():
            required = pattern.get('required', [])
            typical = pattern.get('typical', [])
            may_have = pattern.get('may_have', [])
            should_not_have = pattern.get('should_not_have', [])

            required_hits = [f for f in required if self._feature_present(f, combined_text)]
            typical_hits = [f for f in typical if self._feature_present(f, combined_text)]
            optional_hits = [f for f in may_have if self._feature_present(f, combined_text)]
            contradiction_hits = [f for f in should_not_have if self._feature_present(f, combined_text)]
            missing_required = [f for f in required if f not in required_hits]

            required_ratio = (len(required_hits) / len(required)) if required else 0.5
            typical_ratio = (len(typical_hits) / len(typical)) if typical else 0.0
            optional_ratio = (len(optional_hits) / len(may_have)) if may_have else 0.0

            score = (0.55 * required_ratio) + (0.30 * typical_ratio) + (0.15 * optional_ratio)
            if required and not required_hits:
                score *= 0.40
            score -= 0.18 * len(missing_required)
            score -= 0.12 * len(contradiction_hits)
            score = max(0.0, min(score, 0.92))

            if score < 0.22 and not required_hits:
                continue

            candidates.append({
                'term': self._normalize_condition_name(condition),
                'score': round(score, 2),
                'supporting': [s.replace('_', ' ') for s in (required_hits + typical_hits)][:4],
                'missing': [m.replace('_', ' ') for m in missing_required][:3],
                'contra': [c.replace('_', ' ') for c in contradiction_hits][:2]
            })

        candidates.sort(key=lambda x: x['score'], reverse=True)
        deduped = []
        seen = set()
        for candidate in candidates:
            key = self._canonical_diagnosis(candidate['term'])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
            if len(deduped) >= 6:
                break

        must_not_miss = []
        seen_mnm = set()
        for flag in red_flag_analysis.get('detected_flags', []):
            for dx in flag.get('ddx', []):
                key = self._canonical_diagnosis(dx)
                if key in seen_mnm:
                    continue
                seen_mnm.add(key)
                must_not_miss.append(dx)
                if len(must_not_miss) >= 6:
                    break
            if len(must_not_miss) >= 6:
                break

        return {
            'candidates': deduped,
            'must_not_miss': must_not_miss,
        }

    def _build_hypothesis_context(self, hypotheses: Dict[str, Any], features: List[str]) -> str:
        """Compact heuristic context injected into prompt"""
        lines = ["PRE-LLM HEURISTIC TRIAGE:"]
        if features:
            lines.append(f"- Positive features: {', '.join(features[:10])}")

        if hypotheses.get('candidates'):
            lines.append("- Top pattern-fit candidates:")
            for idx, cand in enumerate(hypotheses['candidates'][:4], 1):
                support = ', '.join(cand['supporting']) if cand['supporting'] else 'limited direct match'
                missing = f"; missing: {', '.join(cand['missing'])}" if cand['missing'] else ''
                lines.append(f"  {idx}. {cand['term']} ({int(cand['score'] * 100)}%) - support: {support}{missing}")

        if hypotheses.get('must_not_miss'):
            lines.append(f"- Must-not-miss due to red flags: {', '.join(hypotheses['must_not_miss'][:4])}")

        return "\n".join(lines)

    def _merge_with_heuristic_differential(
        self, diagnoses: List[Dict[str, Any]], hypotheses: Dict[str, Any], red_flag_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Blend LLM differential with deterministic pattern-fit candidates"""
        merged = list(diagnoses)

        if not merged:
            for cand in hypotheses.get('candidates', [])[:4]:
                merged.append({'term': cand['term'], 'score': max(0.35, min(cand['score'], 0.82))})

        for cand in hypotheses.get('candidates', [])[:4]:
            if any(self._diagnoses_match(cand['term'], d['term']) for d in merged):
                continue
            merged.append({'term': cand['term'], 'score': max(0.35, min(cand['score'] * 0.9, 0.70))})

        if red_flag_analysis.get('has_red_flags'):
            for high_risk in hypotheses.get('must_not_miss', [])[:3]:
                if any(self._diagnoses_match(high_risk, d['term']) for d in merged):
                    continue
                merged.append({'term': high_risk, 'score': 0.34})

        merged.sort(key=lambda x: x.get('score', 0.0), reverse=True)

        deduped = []
        seen = set()
        for item in merged:
            key = self._canonical_diagnosis(item.get('term', ''))
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= 6:
                break

        return deduped

    def _merge_unique_strings(self, primary: List[str], secondary: List[str], limit: int = 8) -> List[str]:
        merged: List[str] = []
        seen = set()
        for source in (primary, secondary):
            for item in source:
                value = re.sub(r'\s+', ' ', str(item or '').strip())
                if not value:
                    continue
                key = value.lower()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(value)
                if len(merged) >= limit:
                    return merged
        return merged

    def _has_mccune_albright_triad(self, combined_text: str) -> bool:
        required_features = ['precocious puberty', 'cafe au lait spots', 'fibrous dysplasia']
        return all(self._feature_present(feature, combined_text) for feature in required_features)

    def _refine_rare_endocrine_pattern(
        self,
        parsed: Dict[str, Any],
        symptoms_text: str,
        clinical_notes: str,
    ) -> None:
        combined_text = f"{symptoms_text} {clinical_notes}".lower().strip()
        if not combined_text:
            return
        if not self._has_mccune_albright_triad(combined_text):
            return

        blocked_terms = ['familial adenomatous polyposis', 'fap']
        curated = [
            ('McCune-Albright syndrome', 0.90),
            ('Fibrous dysplasia (monostotic/polyostotic)', 0.68),
            ('Peripheral precocious puberty (gonadotropin-independent)', 0.62),
            ('Central precocious puberty', 0.55),
            ('Neurofibromatosis type 1 (NF1)', 0.42),
        ]

        refined: List[Dict[str, Any]] = []
        seen = set()
        for term, score in curated:
            key = self._canonical_diagnosis(term)
            if not key or key in seen:
                continue
            seen.add(key)
            refined.append({'term': term, 'score': score})

        for item in parsed.get('diagnoses', []):
            term = str(item.get('term', '')).strip()
            if not term:
                continue
            lower_term = term.lower()
            if any(blocked in lower_term for blocked in blocked_terms):
                continue
            if any(self._diagnoses_match(term, existing.get('term', '')) for existing in refined):
                continue
            key = self._canonical_diagnosis(term)
            if not key or key in seen:
                continue
            try:
                score = float(item.get('score', 0.40))
            except (TypeError, ValueError):
                score = 0.40
            refined.append({'term': term, 'score': max(0.30, min(score, 0.88))})
            seen.add(key)
            if len(refined) >= 5:
                break

        parsed['diagnoses'] = refined[:5]
        parsed['confidence_score'] = max(float(parsed.get('confidence_score', 0.0) or 0.0), 0.82)
        parsed['interpretation'] = (
            'Moderate-high confidence - classic triad supports McCune-Albright syndrome; confirm with focused endocrine and skeletal workup'
        )

        targeted_workup = [
            'Urgent pediatric endocrinology referral; co-manage with orthopedics for fibrous dysplasia burden.',
            'Endocrine panel: LH/FSH, estradiol/testosterone, DHEAS/17-hydroxyprogesterone, TSH/free T4, prolactin, IGF-1.',
            'Bone age radiograph (left hand/wrist) and serial growth velocity/puberty staging.',
            'Targeted pelvic/testicular ultrasound; evaluate adrenal source if androgen excess is suspected.',
            'Skeletal imaging (X-ray/CT or MRI of symptomatic sites) to assess deformity and fracture risk.',
            'GNAS mutation testing; consider tissue-based testing if blood testing is negative but clinical suspicion remains high.',
        ]
        parsed['recommendations'] = self._merge_unique_strings(targeted_workup, parsed.get('recommendations', []), limit=6)

        parsed['doctor_actions'] = [
            'Screen each visit for fracture risk, bone pain progression, visual/hearing symptoms, and neurologic deficits.',
            'Avoid anchoring on isolated precocious puberty until endocrine and skeletal evaluation is completed.',
            'Counsel family that mosaic disorders can have negative blood genetics; tissue testing may be needed.',
            'Set close follow-up (4-8 weeks initially) to review growth trend, pubertal progression, and lab/imaging results.',
        ]

        prior_summary = str(parsed.get('summary', '')).strip()
        focused_summary = (
            'Clinical pattern is highly suggestive of McCune-Albright syndrome (precocious puberty + cafe-au-lait lesions + fibrous dysplasia). '
            'Prioritize endocrine referral, bone-age/hormonal evaluation, and skeletal lesion staging; defer empiric endocrine therapy until specialist assessment.'
        )
        if prior_summary:
            parsed['summary'] = f"{prior_summary} {focused_summary}"
        else:
            parsed['summary'] = focused_summary

    def _contains_any_marker(self, text: str, markers: List[str]) -> bool:
        for marker in markers:
            if self._is_present_and_not_negated(marker, text):
                return True
        return False

    def _extract_numeric_value(self, text: str, patterns: List[str]) -> float:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                continue
        return -1.0

    def _detect_multimorbidity_conditions(self, symptoms_text: str, clinical_notes: str) -> List[Dict[str, Any]]:
        combined = f"{symptoms_text} {clinical_notes}".lower().strip()
        if not combined:
            return []

        conditions: List[Dict[str, Any]] = []

        # Acute COPD exacerbation should be treated as a high-priority active diagnosis.
        has_copd_history = self._contains_any_marker(
            combined,
            ['copd', 'chronic obstructive pulmonary disease', 'chronic bronchitis', 'emphysema'],
        )
        has_dyspnea = self._contains_any_marker(
            combined,
            ['shortness of breath', 'dyspnea', 'difficulty breathing', 'breathlessness'],
        )
        has_cough = self._contains_any_marker(
            combined,
            ['cough', 'productive cough', 'sputum', 'phlegm'],
        )
        has_wheeze_or_crackles = self._contains_any_marker(
            combined,
            ['wheezing', 'wheeze', 'crackles', 'rales'],
        )
        has_fever = self._contains_any_marker(combined, ['fever', 'febrile', 'temperature'])
        spo2_value = self._extract_numeric_value(
            combined,
            [r'(?:spo2|oxygen saturation|o2 sat)\s*(?:of|=|:)?\s*(\d{2,3})'],
        )
        has_hypoxemia = 0 < spo2_value <= 92
        if has_copd_history and has_dyspnea and (has_cough or has_wheeze_or_crackles):
            evidence = ['known COPD']
            if has_dyspnea:
                evidence.append('worsening dyspnea')
            if has_cough:
                evidence.append('productive cough/sputum')
            if has_wheeze_or_crackles:
                evidence.append('wheezing/crackles on exam')
            if has_fever:
                evidence.append('febrile/inflammatory pattern')
            if has_hypoxemia:
                evidence.append(f'SpO2 {spo2_value:g}% on room air')
            conditions.append(
                {
                    'term': 'Acute COPD exacerbation',
                    'score': 0.94 if has_hypoxemia else 0.88,
                    'evidence': evidence[:5],
                }
            )

        # Uncontrolled type 2 diabetes mellitus.
        glucose_value = self._extract_numeric_value(
            combined,
            [
                r'(?:fasting\s+blood\s+glucose|blood\s+glucose|glucose|fbg)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)',
            ],
        )
        hba1c_value = self._extract_numeric_value(
            combined,
            [
                r'(?:hba1c|a1c)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)',
            ],
        )
        has_dm_history = self._contains_any_marker(
            combined,
            ['type 2 diabetes', 't2dm', 'diabetes mellitus', 'diabetic'],
        )
        has_dm_symptoms = (
            self._feature_present('polyuria', combined)
            and self._feature_present('polydipsia', combined)
        )
        has_hyperglycemia = (
            glucose_value >= 200
            or hba1c_value >= 7.0
            or self._feature_present('hyperglycemia', combined)
        )
        if has_hyperglycemia and (has_dm_history or has_dm_symptoms):
            evidence = []
            if has_dm_history:
                evidence.append('known diabetes history')
            if has_dm_symptoms:
                evidence.append('polyuria/polydipsia')
            if glucose_value >= 0:
                evidence.append(f'glucose {glucose_value:g} mg/dL')
            if hba1c_value >= 0:
                evidence.append(f'HbA1c {hba1c_value:g}%')
            if self._contains_any_marker(combined, ['poor adherence', 'nonadherence', 'missed medications']):
                evidence.append('medication non-adherence')
            conditions.append(
                {
                    'term': 'Uncontrolled type 2 diabetes mellitus',
                    'score': 0.82 if hba1c_value >= 8.5 or glucose_value >= 220 else 0.74,
                    'evidence': evidence[:4],
                }
            )

        # Hypertension with renal impairment.
        bp_match = re.search(r'\bbp\s*(?:of|=|:)?\s*(\d{2,3})\s*/\s*(\d{2,3})\b', combined, flags=re.IGNORECASE)
        systolic = -1
        diastolic = -1
        if bp_match:
            try:
                systolic = int(bp_match.group(1))
                diastolic = int(bp_match.group(2))
            except (TypeError, ValueError):
                systolic = -1
                diastolic = -1
        has_htn = self._contains_any_marker(combined, ['hypertension', 'high blood pressure']) or (
            systolic >= 140 or diastolic >= 90
        )
        creatinine_value = self._extract_numeric_value(
            combined,
            [r'(?:serum\s+)?creatinine\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)'],
        )
        egfr_value = self._extract_numeric_value(
            combined,
            [r'(?:egfr|gfr)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)'],
        )
        has_renal_impairment = (
            creatinine_value >= 1.3
            or (0 < egfr_value < 60)
            or self._contains_any_marker(combined, ['renal impairment', 'chronic kidney disease', 'ckd'])
        )
        if has_htn and has_renal_impairment:
            evidence = []
            if systolic > 0 and diastolic > 0:
                evidence.append(f'BP {systolic}/{diastolic}')
            if creatinine_value >= 0:
                evidence.append(f'creatinine {creatinine_value:g} mg/dL')
            if egfr_value >= 0:
                evidence.append(f'eGFR {egfr_value:g} mL/min/1.73m2')
            evidence.append('hypertension with renal involvement')
            conditions.append(
                {
                    'term': 'Hypertension with renal impairment',
                    'score': 0.78 if systolic >= 160 or diastolic >= 100 else 0.72,
                    'evidence': evidence[:4],
                }
            )

        # Acute gout flare.
        uric_value = self._extract_numeric_value(
            combined,
            [r'(?:serum\s+)?uric\s+acid\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)'],
        )
        has_joint_focus = self._contains_any_marker(
            combined,
            ['joint pain', 'acute joint pain', 'podagra', 'metatarsophalangeal', 'great toe pain'],
        )
        has_inflammatory_joint_signs = self._contains_any_marker(
            combined,
            ['swollen', 'erythematous', 'red', 'tender', 'extremely tender', 'warm joint'],
        )
        if has_joint_focus and (has_inflammatory_joint_signs or uric_value >= 7.0):
            evidence = []
            if self._contains_any_marker(combined, ['great toe', 'metatarsophalangeal', 'podagra']):
                evidence.append('first MTP involvement')
            if has_inflammatory_joint_signs:
                evidence.append('swollen/erythematous/tender joint')
            if uric_value >= 0:
                evidence.append(f'uric acid {uric_value:g} mg/dL')
            conditions.append(
                {
                    'term': 'Acute gout flare',
                    'score': 0.86 if uric_value >= 8.0 else 0.78,
                    'evidence': evidence[:4],
                }
            )

        # Rhythm issue should remain in differential if explicitly documented.
        if self._contains_any_marker(
            combined,
            ['irregular rhythm', 'premature atrial contractions', 'palpitations'],
        ):
            conditions.append(
                {
                    'term': 'Cardiac rhythm disturbance (premature atrial contractions)',
                    'score': 0.56,
                    'evidence': ['palpitations/irregular rhythm documented'],
                }
            )

        if self._contains_any_marker(combined, ['ankle swelling', 'peripheral edema', 'pedal edema']):
            conditions.append(
                {
                    'term': 'Peripheral edema (evaluate cardiorenal cause)',
                    'score': 0.54,
                    'evidence': ['ankle/peripheral edema documented'],
                }
            )

        conditions.sort(key=lambda item: item.get('score', 0.0), reverse=True)
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for item in conditions:
            key = self._canonical_diagnosis(item.get('term', ''))
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= 6:
                break
        return deduped

    def _has_allergy(self, combined_text: str, markers: List[str]) -> bool:
        return self._contains_any_marker(combined_text, markers)

    def _build_parallel_management_guidance(self, active_terms: List[str], combined_text: str) -> Tuple[List[str], List[str]]:
        lower_terms = [self._canonical_diagnosis(item) for item in active_terms]
        has_copd = any('acute copd exacerbation' in item or item == 'copd' for item in lower_terms)
        has_dm = any('type 2 diabetes' in item or 'uncontrolled' in item for item in lower_terms)
        has_htn_renal = any('hypertension with renal impairment' in item for item in lower_terms)
        has_gout = any('gout' in item for item in lower_terms)

        has_acei_allergy = self._has_allergy(
            combined_text,
            ['ace inhibitor allergy', 'allergy to ace inhibitor', 'angioedema from ace', 'facial swelling from ace'],
        )
        has_penicillin_allergy = self._has_allergy(
            combined_text,
            ['penicillin allergy', 'allergy to penicillin', 'penicillin caused hives', 'penicillin caused swelling'],
        )
        has_nsaid_allergy = self._has_allergy(
            combined_text,
            ['nsaid allergy', 'allergy to nsaid', 'ibuprofen allergy', 'naproxen allergy'],
        )

        recommendations: List[str] = []
        actions: List[str] = []

        if has_copd:
            recommendations.extend(
                [
                    'Treat acute COPD exacerbation first: short-acting bronchodilator regimen and oxygen titration (target SpO2 about 88-92%).',
                    'Consider short-course systemic corticosteroid if no contraindication; monitor for steroid-induced hyperglycemia.',
                    'If bacterial trigger is likely (purulent sputum/raised inflammatory markers), choose non-penicillin antibiotics when penicillin allergy is present.',
                ]
            )
            actions.append('Escalate urgently if respiratory distress worsens, oxygen requirement rises, or mental status changes.')

        if has_dm:
            recommendations.append('Check serial capillary glucose and intensify glycemic control (often temporary insulin-based correction in acute illness).')
            actions.append('Set explicit glucose targets and monitor closely while on steroids or during infection.')

        if has_htn_renal:
            if has_acei_allergy:
                recommendations.append('Use a non-ACE-inhibitor blood pressure strategy due documented ACE-related reaction; monitor creatinine/eGFR and potassium.')
            else:
                recommendations.append('Adjust antihypertensive regimen with renal-safe dosing; monitor creatinine/eGFR and electrolytes.')
            actions.append('Track fluid status and edema trend to separate cardiorenal vs inflammatory contributors.')

        if has_gout:
            if has_nsaid_allergy:
                recommendations.append('Avoid NSAIDs due allergy; consider colchicine or corticosteroid strategy with renal-adjusted dosing.')
            else:
                recommendations.append('For acute gout flare, use renal-adjusted anti-inflammatory treatment and avoid nephrotoxic combinations.')

        if has_nsaid_allergy and has_copd:
            recommendations.append('Use acetaminophen for pain/fever control instead of NSAIDs when clinically appropriate.')

        recommendations = self._merge_unique_strings(recommendations, [], limit=8)
        actions = self._merge_unique_strings(
            [
                'Do not collapse clearly concurrent active diseases into a single label when objective data supports multimorbidity.',
                'Reconcile allergy list before final medication orders and discharge counseling.',
            ],
            actions,
            limit=7,
        )
        return recommendations, actions

    def _apply_multimorbidity_adjustments(self, parsed: Dict[str, Any], symptoms_text: str, clinical_notes: str) -> None:
        active_conditions = self._detect_multimorbidity_conditions(symptoms_text, clinical_notes)
        if not active_conditions:
            return

        combined_text = f"{symptoms_text} {clinical_notes}".lower()
        active_conditions_sorted = sorted(
            active_conditions,
            key=lambda item: float(item.get('score', 0.0)),
            reverse=True,
        )
        parsed['active_diagnoses'] = [item['term'] for item in active_conditions_sorted]
        existing = list(parsed.get('diagnoses', []))
        reordered: List[Dict[str, Any]] = []

        # Keep strongly supported active conditions at the top for multimorbidity cases.
        for item in active_conditions_sorted:
            reordered.append({'term': item['term'], 'score': float(item.get('score', 0.65))})

        for diag in existing:
            term = str(diag.get('term', '')).strip()
            if not term:
                continue
            if any(self._diagnoses_match(term, dx['term']) for dx in reordered):
                continue
            score = float(diag.get('score', 0.45) or 0.45)
            # Prevent unrelated respiratory anchor from dominating without supporting pattern.
            if 'pneumonia' in term.lower():
                has_cxr_no_consolidation = self._contains_any_marker(
                    combined_text,
                    ['no focal consolidation', 'no consolidation', 'without focal consolidation'],
                )
                lacks_support = not self._feature_present('cough', combined_text) and not self._feature_present('productive cough', combined_text)
                if has_cxr_no_consolidation:
                    score = min(score, 0.30)
                elif lacks_support:
                    score = min(score, 0.34)
            if 'acute copd exacerbation' in term.lower():
                # Keep acute respiratory diagnosis near the top when present.
                score = max(score, 0.86)
            if 'uncontrolled type 2 diabetes mellitus' in term.lower() and any(
                'acute copd exacerbation' in c.get('term', '').lower() for c in active_conditions_sorted
            ):
                score = min(score, 0.82)
            if 'hypertension with renal impairment' in term.lower() and any(
                'acute copd exacerbation' in c.get('term', '').lower() for c in active_conditions_sorted
            ):
                score = min(score, 0.78)
            reordered.append({'term': term, 'score': score})

        reordered.sort(key=lambda item: item.get('score', 0.0), reverse=True)
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for item in reordered:
            key = self._canonical_diagnosis(item.get('term', ''))
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= 6:
                break
        parsed['diagnoses'] = deduped

        if len(active_conditions_sorted) >= 2:
            parsed['confidence_score'] = max(float(parsed.get('confidence_score', 0.0) or 0.0), 0.72)
            parsed['interpretation'] = (
                'Moderate-high confidence - multiple concurrent active conditions detected; manage in parallel and confirm with targeted tests'
            )

            multitarget_workup, multitarget_actions = self._build_parallel_management_guidance(
                parsed.get('active_diagnoses', []),
                combined_text,
            )
            parsed['recommendations'] = self._merge_unique_strings(
                multitarget_workup,
                parsed.get('recommendations', []),
                limit=8,
            )

            parsed['doctor_actions'] = self._merge_unique_strings(
                multitarget_actions,
                parsed.get('doctor_actions', []),
                limit=6,
            )

            active_terms = ', '.join(parsed['active_diagnoses'][:4])
            summary_text = (
                f"Case is most consistent with concurrent active conditions: {active_terms}. "
                "Management should run in parallel rather than anchoring on a single diagnosis."
            )
            previous_summary = str(parsed.get('summary', '')).strip()
            if previous_summary:
                parsed['summary'] = f"{summary_text} {previous_summary}"
            else:
                parsed['summary'] = summary_text

    def _line_to_heading_key(self, line: str) -> str:
        """Normalize a line to a known section heading key when possible"""
        normalized = line.strip().lower()
        normalized = re.sub(r'^\d+\.\s*', '', normalized)
        normalized = normalized.replace('#', '').replace('*', '')
        normalized = normalized.strip(': ').strip()
        normalized = re.sub(r'\s+', ' ', normalized)

        heading_map = {
            'urgent alert': 'urgent',
            'primary diagnosis': 'primary',
            'why this fits': 'why',
            'differential diagnoses': 'differential',
            'differential diagnosis': 'differential',
            'differential': 'differential',
            'confidence': 'confidence',
            'recommended workup': 'workup',
            'workup': 'workup',
            'medication recommendations': 'medications',
            'medications': 'medications',
            'clinical summary': 'summary',
            'summary': 'summary',
        }

        for heading, key in heading_map.items():
            if normalized.startswith(heading):
                return key
        return ''

    def _extract_section(self, response: str, target_keys: List[str]) -> str:
        """Extract a section body based on normalized heading keys"""
        lines = response.splitlines()
        capturing = False
        collected = []

        for raw_line in lines:
            key = self._line_to_heading_key(raw_line)
            if key:
                if capturing:
                    break
                if key in target_keys:
                    capturing = True
                    inline_match = re.search(r':\s*(.+)$', raw_line.strip())
                    if inline_match:
                        inline_text = inline_match.group(1).strip()
                        if inline_text and inline_text != raw_line.strip():
                            collected.append(inline_text)
                continue

            if capturing:
                collected.append(raw_line)

        return '\n'.join(collected).strip()
    
    def _is_present_and_not_negated(self, keyword: str, text: str) -> bool:
        """Check if keyword exists and is NOT negated (e.g. 'denies chest pain')"""
        if keyword not in text:
            return False
            
        # Common clinical negation patterns
        # Uses word boundaries (\b) to ensure we don't match partial words
        escaped_keyword = re.escape(keyword)
        negation_patterns = [
            r'\bno\s+' + escaped_keyword + r'\b',           # "no chest pain"
            r'\bdenies\s+' + escaped_keyword + r'\b',       # "denies chest pain"
            r'\bwithout\s+' + escaped_keyword + r'\b',      # "without chest pain"
            r'\babsent\s+' + escaped_keyword + r'\b',       # "absent chest pain"
            r'\bnegative\s+for\s+' + escaped_keyword + r'\b', # "negative for chest pain"
            r'\bnot\s+' + escaped_keyword + r'\b'           # "not chest pain"
        ]
        
        # If any negation pattern matches, return False (it IS negated)
        is_negated = any(re.search(p, text) for p in negation_patterns)
        return not is_negated

    def detect_red_flags(self, symptoms_text: str, clinical_notes: str = "") -> Dict[str, Any]:
        """Detect life-threatening or urgent symptoms with negation handling"""
        combined_text = f"{symptoms_text} {clinical_notes}".lower()
        detected_flags = []
        urgency_level = "ROUTINE"
        
        # 1. Check single red flags
        for flag_name, flag_data in self.red_flag_patterns.items():
            if flag_name == 'multiple_bleeding_sites':
                continue  # Handle separately

            if flag_name == 'chest_pain_dyspnea':
                has_chest_pain = self._contains_any_marker(
                    combined_text,
                    ['chest pain', 'chest discomfort', 'chest pressure', 'chest tightness'],
                )
                has_dyspnea = self._contains_any_marker(
                    combined_text,
                    ['shortness of breath', 'dyspnea', 'difficulty breathing', 'breathlessness'],
                )
                spo2_value = self._extract_numeric_value(
                    combined_text,
                    [r'(?:spo2|oxygen saturation|o2 sat)\s*(?:of|=|:)?\s*(\d{2,3})'],
                )
                has_hypoxemia = 0 < spo2_value <= 90

                if not ((has_chest_pain and has_dyspnea) or has_hypoxemia):
                    continue

                matched_keyword = 'chest pain + dyspnea' if (has_chest_pain and has_dyspnea) else f'hypoxemia (SpO2 {spo2_value:g}%)'
                detected_flags.append({
                    'flag': flag_name,
                    'keyword': matched_keyword,
                    'severity': flag_data['severity'],
                    'ddx': flag_data['ddx'],
                    'workup': flag_data['workup']
                })
                if flag_data['severity'] == 'URGENT':
                    urgency_level = 'URGENT'
                elif flag_data['severity'] == 'HIGH' and urgency_level == 'ROUTINE':
                    urgency_level = 'HIGH'
                continue
            
            keywords = flag_data.get('keywords', [])
            matched = False
            matched_keyword = None
            
            for keyword in keywords:
                # Check exact match first
                if self._is_present_and_not_negated(keyword, combined_text):
                    matched = True
                    matched_keyword = keyword
                    break
                
                # Check variations (e.g. "nose bleed" -> "epistaxis")
                variations = self._get_symptom_variations(keyword)
                for var in variations:
                    if self._is_present_and_not_negated(var, combined_text):
                        matched = True
                        matched_keyword = var  # Use the variation found
                        break
                
                if matched:
                    break
            
            if matched:
                detected_flags.append({
                    'flag': flag_name,
                    'keyword': matched_keyword,
                    'severity': flag_data['severity'],
                    'ddx': flag_data['ddx'],
                    'workup': flag_data['workup']
                })
                # Update urgency level
                if flag_data['severity'] == 'URGENT':
                    urgency_level = 'URGENT'
                elif flag_data['severity'] == 'HIGH' and urgency_level == 'ROUTINE':
                    urgency_level = 'HIGH'
        
        # 2. Check combined patterns (multiple bleeding sites)
        if 'multiple_bleeding_sites' in self.red_flag_patterns:
            combined_patterns = self.red_flag_patterns['multiple_bleeding_sites']['combined_keywords']
            
            for pattern_group in combined_patterns:
                # pattern_group is a list of symptom groups: 
                # [['coughing blood', 'hemoptysis'], ['nose bleed', 'epistaxis']]
                
                # We need to find ONE match from Group A AND ONE match from Group B
                match_count = 0
                matched_keywords = []

                # iterate through the groups (e.g. Group A is coughing/hemoptysis)
                for symptom_options in pattern_group:
                    group_match_found = False
                    
                    # Check if ANY option in this group exists
                    # Handle both single string "coughing blood" and list ['coughing blood']
                    options_to_check = [symptom_options] if isinstance(symptom_options, str) else symptom_options
                    
                    for option in options_to_check:
                         # Get variations for this specific option
                        variations = self._get_symptom_variations(option)
                        
                        # Check all variations
                        for var in variations:
                            if self._is_present_and_not_negated(var, combined_text):
                                group_match_found = True
                                matched_keywords.append(var)
                                break
                        if group_match_found:
                            break
                    
                    if group_match_found:
                        match_count += 1
                
                # If we found matches for ALL groups in the pattern (e.g. both coughing AND nosebleed)
                if match_count == len(pattern_group):
                    detected_flags.append({
                        'flag': 'multiple_bleeding_sites',
                        'keyword': ' + '.join(matched_keywords),
                        'severity': 'URGENT',
                        'ddx': self.red_flag_patterns['multiple_bleeding_sites']['ddx'],
                        'workup': self.red_flag_patterns['multiple_bleeding_sites']['workup']
                    })
                    urgency_level = 'URGENT'
                    break
        
        return {
            'has_red_flags': len(detected_flags) > 0,
            'urgency_level': urgency_level,
            'detected_flags': detected_flags
        }
        
    def _get_symptom_variations(self, symptom: str) -> List[str]:
        """Generate common variations of a symptom for fuzzy matching"""
        variations = [symptom]  # Start with original
        
        # Define synonym mappings
        synonym_map = {
            'cough': ['coughing', 'coughs'],
            'chronic cough': ['chronic coughing', 'persistent cough', 'prolonged cough'],
            'dyspnea': ['shortness of breath', 'difficulty breathing', 'breathlessness', 'sob'],
            'shortness of breath': ['dyspnea', 'difficulty breathing', 'breathlessness', 'sob'],
            'dyspnea on exertion': ['shortness of breath on exertion', 'exertional dyspnea', 'doe'],
            'chest pain': ['chest discomfort', 'chest pressure', 'chest tightness'],
            'abdominal pain': ['stomach pain', 'belly pain', 'abdominal discomfort', 'tummy pain'],
            'hemoptysis': ['coughing blood', 'coughing up blood', 'blood in sputum', 'bloody cough'],
            'coughing blood': ['hemoptysis', 'coughing up blood', 'blood in sputum'],
            'productive cough': ['productive sputum', 'phlegm', 'yellow green sputum', 'purulent sputum'],
            'sputum production': ['productive cough', 'phlegm', 'mucus'],
            'epistaxis': ['nose bleed', 'nosebleed', 'nose bleeding', 'nasal bleeding'],
            'nose bleed': ['epistaxis', 'nosebleed', 'nose bleeding', 'nasal bleeding'],
            'nosebleed': ['epistaxis', 'nose bleed', 'nose bleeding', 'nasal bleeding'],
            'swelling': ['edema', 'swollen', 'puffiness', 'inflammation'],
            'edema': ['swelling', 'swollen', 'puffiness'],
            'vomiting': ['vomit', 'vomits', 'throwing up', 'emesis'],
            'diarrhea': ['loose stools', 'watery stools', 'frequent bowel movements'],
            'constipation': ['hard stools', 'infrequent bowel movements', 'difficulty passing stool'],
            'fever': ['febrile', 'temperature', 'high temperature', 'pyrexia', 'lagnat'],
            'fatigue': ['tiredness', 'tired', 'exhaustion', 'exhausted', 'weakness'],
            'headache': ['head pain', 'cephalgia'],
            'nausea': ['nauseous', 'queasy', 'sick to stomach'],
            'dizziness': ['dizzy', 'lightheaded', 'vertigo', 'spinning'],
            'weight loss': ['losing weight', 'unintentional weight loss', 'dropped weight'],
            'night sweats': ['nocturnal sweating', 'sweating at night'],
            'rhinorrhea': ['runny nose', 'nasal discharge', 'sipon'],
            'runny nose': ['rhinorrhea', 'nasal discharge', 'sipon'],
            'nasal congestion': ['stuffy nose', 'blocked nose', 'baradong ilong'],
            'nasal symptoms': ['runny nose', 'rhinorrhea', 'nasal congestion', 'sneezing', 'sipon'],
            'wheezing': ['wheeze', 'whistling breath'],
            'crackles': ['rales', 'basal crackles'],
            'hypoxemia': ['low oxygen saturation', 'low spo2', 'desaturation'],
            'body aches': ['myalgia', 'muscle pain', 'body pain', 'sakit ng katawan', 'pananakit ng katawan'],
            'myalgia': ['body aches', 'muscle aches', 'muscle pain', 'sakit ng katawan'],
            'sore throat': ['throat pain', 'masakit ang lalamunan'],
            'depressed mood': ['persistent depressed mood', 'low mood', 'sad mood', 'depression'],
            'anhedonia': ['diminished interest', 'loss of interest', 'loss of pleasure'],
            'insomnia': ['early morning awakening', 'sleep disturbance', 'difficulty sleeping'],
            'worthlessness': ['feelings of worthlessness', 'excessive guilt', 'guilt'],
            'poor concentration': ['difficulty concentrating', 'indecisiveness', 'poor focus'],
            'psychomotor retardation': ['slowed speech', 'slowed movements', 'psychomotor slowing'],
            'suicidal ideation': ['suicidal thoughts', 'thoughts of death', 'self harm', 'self-harm'],
            'precocious puberty': ['early puberty', 'premature puberty', 'sexual precocity'],
            'cafe au lait spots': ['cafe-au-lait spots', 'cafe au lait', 'light brown patches', 'hyperpigmented macules'],
            'fibrous dysplasia': ['polyostotic fibrous dysplasia', 'monostotic fibrous dysplasia', 'bone fibrous dysplasia'],
            'endocrine hyperfunction': ['hormonal hyperfunction', 'autonomous endocrine hyperfunction'],
            'advanced bone age': ['bone age advancement', 'advanced skeletal age'],
            'gi symptoms': ['gastrointestinal symptoms', 'stomach problems', 'digestive issues', 
                           'gi issues', 'abdominal symptoms'],
            'abnormal bleeding': ['bleeding disorder', 'excessive bleeding', 'prolonged bleeding',
                                'spontaneous bleeding'],
            'bleeding': ['hemorrhage', 'blood loss'],
            'hyperglycemia': [
                'high blood glucose',
                'high blood sugar',
                'elevated glucose',
                'fasting blood glucose',
                'fbg',
                'hba1c',
                'elevated hba1c',
                'poor glycemic control',
                'uncontrolled diabetes',
            ],
            'elevated hba1c': ['hba1c', 'glycated hemoglobin', 'a1c'],
            'hypertension': ['high blood pressure', 'bp', 'elevated blood pressure'],
            'renal impairment': [
                'kidney impairment',
                'renal dysfunction',
                'chronic kidney disease',
                'reduced egfr',
                'egfr',
                'elevated creatinine',
            ],
            'elevated creatinine': ['creatinine', 'high creatinine'],
            'reduced egfr': ['low egfr', 'egfr', 'reduced gfr'],
            'acute joint pain': ['sudden joint pain', 'acute monoarthritis', 'joint pain'],
            'great toe pain': ['big toe pain', '1st mcp pain', 'podagra', 'first metatarsophalangeal pain'],
            'mcp1 swelling': ['first mcp swelling', 'swollen great toe joint', 'swollen mcp'],
            'joint tenderness': ['tender joint', 'extremely tender', 'painful to touch'],
            'warm joint': ['hot joint', 'warmth over joint'],
            'hyperuricemia': ['elevated uric acid', 'serum uric acid', 'high uric acid'],
            'poor medication adherence': ['poor adherence', 'nonadherence', 'non-adherence', 'missed medications'],
            'peripheral edema': ['ankle swelling', 'leg swelling', 'pedal edema'],
        }
        
        # Add synonyms if available
        if symptom in synonym_map:
            variations.extend(synonym_map[symptom])
        
        # Add plural variations
        if not symptom.endswith('s'):
            variations.append(symptom + 's')
        
        # Add gerund form for verbs (if applicable)
        if ' ' not in symptom and not symptom.endswith('ing'):
            variations.append(symptom + 'ing')
        
        return list(set(variations))  # Remove duplicates
    
    def validate_diagnosis_pattern(self, diagnosis: str, symptoms_text: str) -> Tuple[bool, str]:
        """Validate if diagnosis matches expected symptom pattern"""
        diagnosis_lower = diagnosis.lower()
        symptoms_lower = symptoms_text.lower()
        
        # Check against known patterns
        matched_pattern = None
        for condition, pattern in self.symptom_clusters.items():
            condition_phrase = condition.replace('_', ' ')
            if (
                condition in diagnosis_lower
                or condition_phrase in diagnosis_lower
                or diagnosis_lower in condition
                or diagnosis_lower in condition_phrase
            ):
                matched_pattern = (condition, pattern)
                break
        
        if matched_pattern:
            condition, pattern = matched_pattern
            
            # Check required features
            required = pattern.get('required', [])
            missing_required = []
            for req in required:
                # Convert underscore to space for matching
                req_phrase = req.replace('_', ' ')
                
                # Use exact phrase matching (not individual word matching)
                # This prevents false positives like "chest" matching when we need "chest pain"
                if req_phrase not in symptoms_lower:
                    # Also check for common variations
                    req_variations = self._get_symptom_variations(req_phrase)
                    if not any(var in symptoms_lower for var in req_variations):
                        missing_required.append(req)
            
            if missing_required:
                return False, f"Missing required features for {condition}: {', '.join(missing_required)}"
            
            # Check contraindications (should_not_have)
            should_not_have = pattern.get('should_not_have', [])
            for contraindication in should_not_have:
                contra_terms = contraindication.replace('_', ' ')
                if contra_terms in symptoms_lower:
                    return False, f"{condition} should not present with {contra_terms}"
            
            # Check lab requirements if specified
            should_not_diagnose_if = pattern.get('should_not_diagnose_if', [])
            for exclusion_criteria in should_not_diagnose_if:
                if exclusion_criteria.lower() in symptoms_lower:
                    return False, f"Cannot diagnose {condition}: {exclusion_criteria}"
            
            return True, f"Pattern matches {condition}"
        
        # No specific pattern defined - apply default strict validation
        # Check for red flag symptoms with benign diagnosis
        benign_conditions = [
            'simple', 'benign', 'non-specific', 'functional', 'idiopathic',
            'mild', 'minor', 'common cold', 'viral syndrome'
        ]
        
        red_flag_symptoms = [
            'hemoptysis', 'coughing blood', 'epistaxis', 'nose bleed',
            'chest pain', 'severe headache', 'altered mental', 'confusion',
            'weight loss', 'night sweats', 'chronic bleeding',
            'suicidal ideation', 'suicidal thoughts', 'thoughts of death', 'self harm', 'self-harm'
        ]
        
        is_benign = any(term in diagnosis_lower for term in benign_conditions)
        has_red_flags = any(symptom in symptoms_lower for symptom in red_flag_symptoms)
        
        if is_benign and has_red_flags:
            return False, f"Benign diagnosis '{diagnosis}' inappropriate with red flag symptoms present"
        
        # Allow diagnosis but note lack of pattern validation
        return True, f"No specific pattern validation available for {diagnosis}"
    
    def _call_llm(self, user_prompt: str, max_tokens: int = 1500) -> str:
        """Call Med42 via Hugging Face InferenceClient"""
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,  # Lower for more consistent clinical reasoning
                top_p=0.75,
            )
            
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ERROR] API Error: {e}")
            return f"Error calling API: {str(e)}"
    
    def analyze_symptoms(self, symptoms_text: str, clinical_notes: str = "") -> Dict[str, Any]:
        """Analyze symptoms with red flag detection and pattern validation"""
        try:
            normalized_symptoms = self._normalize_multilingual_symptoms(symptoms_text)
            normalized_notes = self._normalize_multilingual_symptoms(clinical_notes)

            analysis_symptoms = normalized_symptoms or str(symptoms_text or '').strip()
            analysis_notes = normalized_notes or str(clinical_notes or '').strip()

            # Step 1: Red flag detection
            red_flag_analysis = self.detect_red_flags(analysis_symptoms, analysis_notes)
            keywords = self._extract_clinical_features(analysis_symptoms, analysis_notes)
            hypotheses = self._build_pre_diagnostic_hypotheses(analysis_symptoms, analysis_notes, red_flag_analysis)
            
            print("Analyzing with Med42-v3 (Red Flag Detection + Pattern Validation)...")
            
            if red_flag_analysis['has_red_flags']:
                print(f"[WARNING] RED FLAGS DETECTED: {red_flag_analysis['urgency_level']}")
                for flag in red_flag_analysis['detected_flags']:
                    print(f"   - {flag['flag']}: {flag['keyword']}")
            
            # Step 2: Build compact prompt context
            full_text = f"Patient presents with: {analysis_symptoms}"
            if analysis_notes:
                full_text += f"\n\nClinical observations: {analysis_notes}"

            original_symptoms = str(symptoms_text or '').strip()
            if original_symptoms and original_symptoms.lower() != analysis_symptoms.lower():
                full_text += f"\n\nOriginal patient wording: {original_symptoms}"
            
            # Add red flag context to LLM
            if red_flag_analysis['has_red_flags']:
                red_flag_context = self._build_red_flag_context(red_flag_analysis)
                full_text += f"\n\n{red_flag_context}"

            # Add deterministic pre-LLM pattern-fit context
            hypothesis_context = self._build_hypothesis_context(hypotheses, keywords)
            full_text += f"\n\n{hypothesis_context}"
            
            # Step 3: Get LLM analysis
            analysis = self._get_comprehensive_analysis(full_text, red_flag_analysis, hypotheses)
            
            if analysis.lower().startswith("error"):
                return self._build_error_response(analysis)
            
            # Step 4: Parse and validate response
            parsed = self._parse_comprehensive_response(analysis)
            parsed['diagnoses'] = self._merge_with_heuristic_differential(
                parsed.get('diagnoses', []), hypotheses, red_flag_analysis
            )
            
            # Step 5: Validate primary diagnosis against symptom patterns
            if parsed['diagnoses']:
                primary_dx = parsed['diagnoses'][0]['term']
                combined_input = f"{analysis_symptoms} {analysis_notes}".strip()
                is_valid, validation_msg = self.validate_diagnosis_pattern(primary_dx, combined_input)
                
                if not is_valid:
                    print(f"[WARNING] VALIDATION WARNING: {validation_msg}")
                    parsed['validation_warning'] = validation_msg
                    # Reduce confidence if pattern doesn't match
                    parsed['confidence_score'] = min(parsed['confidence_score'], 0.40)
                    parsed['interpretation'] = f"Low confidence - {validation_msg}"

                    top_candidate = next(
                        (
                            cand for cand in hypotheses.get('candidates', [])
                            if isinstance(cand, dict) and cand.get('term')
                        ),
                        None,
                    )
                    if top_candidate and not self._diagnoses_match(primary_dx, top_candidate.get('term', '')):
                        promoted_term = str(top_candidate.get('term', '')).strip()
                        try:
                            heuristic_score = float(top_candidate.get('score', 0.5))
                        except (TypeError, ValueError):
                            heuristic_score = 0.5
                        promoted_score = max(
                            parsed['confidence_score'],
                            min(heuristic_score, 0.88),
                        )
                        if promoted_term:
                            remaining = [
                                diag for diag in parsed['diagnoses']
                                if not self._diagnoses_match(diag.get('term', ''), promoted_term)
                            ]
                            parsed['diagnoses'] = [{'term': promoted_term, 'score': promoted_score}] + remaining[:5]

            # Step 5b: Calibrate psychiatric risk cases with explicit suicidality
            if parsed.get('diagnoses'):
                primary_dx = str(parsed['diagnoses'][0].get('term', '')).lower()
                combined_case = f"{analysis_symptoms} {analysis_notes}".lower()
                if 'depress' in primary_dx or 'major depressive' in primary_dx:
                    depression_feature_count = self._count_depression_features(combined_case)
                    has_suicidality = self._has_suicidality(combined_case)
                    if has_suicidality and depression_feature_count >= 5:
                        parsed['confidence_score'] = max(parsed['confidence_score'], 0.78)
                        parsed['interpretation'] = (
                            'Moderate-high confidence - severe depressive episode with suicide risk; urgent psychiatric care required'
                        )

            # Step 5c: Refine specific rare-pattern cases for safer differentials and clinician guidance
            self._refine_rare_endocrine_pattern(parsed, analysis_symptoms, analysis_notes)

            # Step 5d: Support multimorbidity cases (multiple active diagnoses in one patient)
            self._apply_multimorbidity_adjustments(parsed, analysis_symptoms, analysis_notes)
            
            # Step 6: Normalize medications and apply fallback if safe
            parsed['medications'] = self._normalize_medications(parsed.get('medications', []))
            if not parsed['medications'] and parsed['diagnoses']:
                fallback_meds = self._build_fallback_medications(
                    parsed['diagnoses'][0]['term'],
                    red_flag_analysis,
                    f"{analysis_symptoms} {analysis_notes}",
                    parsed.get('active_diagnoses', []),
                )
                if fallback_meds:
                    parsed['medications'] = fallback_meds

            # Step 7: Build concise doctor-facing report
            doctor_report = self._build_doctor_facing_reasoning(parsed, red_flag_analysis, hypotheses)
            
            # Step 8: Build final results
            results = {
                'confidence_score': parsed['confidence_score'],
                'suggested_diagnoses': parsed['diagnoses'],
                'keywords': keywords,
                'interpretation': parsed['interpretation'],
                'clinical_reasoning': doctor_report,
                'raw_clinical_reasoning': analysis,
                'summary': parsed.get('summary', ''),
                'recommendations': parsed['recommendations'],
                'medications': parsed['medications'],
                'active_diagnoses': parsed.get('active_diagnoses', []),
                'red_flag_analysis': red_flag_analysis,
                'validation_warning': parsed.get('validation_warning', None)
            }
            
            # Print summary
            print("Analysis complete")
            if parsed['diagnoses']:
                print(f"  Primary Dx: {parsed['diagnoses'][0]['term']}")
                print(f"  Confidence: {parsed['confidence_score']:.1%}")
            print(f"  Urgency: {red_flag_analysis['urgency_level']}")
            if parsed['medications']:
                print(f"  Medications: {len(parsed['medications'])} suggested")
            
            return results
            
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            return self._build_error_response(str(e))

    def _has_suicidality(self, text: str) -> bool:
        markers = [
            'suicidal ideation',
            'suicidal thoughts',
            'thoughts of death',
            'recurrent thoughts of death',
            'self harm',
            'self-harm',
            'wants to die',
        ]
        return any(self._is_present_and_not_negated(marker, text) for marker in markers)

    def _count_depression_features(self, text: str) -> int:
        feature_groups = [
            ['depressed mood', 'persistent depressed mood', 'low mood', 'sad mood'],
            ['anhedonia', 'diminished interest', 'loss of interest', 'loss of pleasure'],
            ['weight loss', 'unintentional weight loss', 'appetite loss'],
            ['insomnia', 'early morning awakening', 'sleep disturbance'],
            ['psychomotor retardation', 'slowed speech', 'slowed movements', 'psychomotor slowing'],
            ['fatigue', 'loss of energy', 'exhaustion'],
            ['worthlessness', 'excessive guilt', 'guilt'],
            ['difficulty concentrating', 'indecisiveness', 'poor concentration'],
        ]
        score = 0
        for group in feature_groups:
            if any(self._is_present_and_not_negated(marker, text) for marker in group):
                score += 1
        return score
    
    def _build_red_flag_context(self, red_flag_analysis: Dict) -> str:
        """Build context for LLM about detected red flags"""
        lines = ["RED FLAG CONTEXT:"]
        for flag in red_flag_analysis.get('detected_flags', []):
            lines.append(
                f"- {flag['flag'].replace('_', ' ')} ({flag['severity']}): "
                f"consider {', '.join(flag.get('ddx', [])[:3])}; "
                f"priority tests: {', '.join(flag.get('workup', [])[:3])}"
            )
        lines.append("Avoid benign diagnoses until serious etiologies are excluded.")
        return "\n".join(lines)
    
    def _get_comprehensive_analysis(
        self, clinical_presentation: str, red_flag_analysis: Dict[str, Any], hypotheses: Dict[str, Any]
    ) -> str:
        """Get concise, doctor-readable analysis with token-aware prompt sizing"""

        max_case_chars = 2400
        max_prompt_chars = 4600

        if len(clinical_presentation) > max_case_chars:
            clinical_presentation = clinical_presentation[:max_case_chars] + "\n[... truncated for token budget ...]"

        urgency_instruction = ""
        if red_flag_analysis.get('has_red_flags'):
            flag_names = [f['flag'].replace('_', ' ') for f in red_flag_analysis.get('detected_flags', [])]
            urgency_instruction = (
                f"URGENT RED FLAGS: {', '.join(flag_names[:3])}. "
                "Prioritize life-threatening causes and urgent workup."
            )

        must_not_miss = hypotheses.get('must_not_miss', [])
        risk_instruction = ""
        if must_not_miss:
            risk_instruction = f"Must-not-miss conditions to address: {', '.join(must_not_miss[:4])}."

        user_prompt = f"""CLINICAL CASE
{clinical_presentation}

SAFETY FOCUS
{urgency_instruction}
{risk_instruction}

TASK
Use the required response format exactly.
Explicitly show:
- why the primary diagnosis fits,
- what competing diagnoses remain possible,
- why confidence is calibrated at that level,
- medication safety boundaries.

Keep output concise, clinically actionable, and doctor-readable."""

        if len(user_prompt) > max_prompt_chars:
            user_prompt = user_prompt[:max_prompt_chars] + "\n[Prompt trimmed to fit token budget]"

        return self._call_llm(user_prompt, max_tokens=900)
    
    def _parse_comprehensive_response(self, response: str) -> Dict[str, Any]:
        """Parse Med42 response with section-aware extraction and safer defaults"""

        diagnoses = []
        confidence_score = 0.50
        interpretation = "Moderate confidence"

        # PRIMARY DIAGNOSIS
        primary_text = self._extract_section(response, ['primary'])
        if primary_text:
            for line in primary_text.splitlines():
                candidate = re.sub(r'^[-•*\d]+[.\)]?\s*', '', line.strip())
                candidate = re.sub(r'\s+', ' ', candidate).strip(' -')
                if candidate and len(candidate) > 3:
                    diagnoses.append({'term': candidate, 'score': 0.85})
                    break

        if not diagnoses:
            primary_patterns = [
                r'(?:primary diagnosis|most likely diagnosis|primary impression)[:\s]*(?:\*\*)?([^*\n]+?)(?:\*\*)?(?:\n|$)',
            ]
            for pattern in primary_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    primary = re.sub(r'^[-•*\d]+[.\)]?\s*', '', match.group(1).strip())
                    primary = re.sub(r'\s+', ' ', primary).strip(' -')
                    if primary and len(primary) > 3:
                        diagnoses.append({'term': primary, 'score': 0.85})
                        break

        # DIFFERENTIAL
        diff_text = self._extract_section(response, ['differential'])
        if diff_text:
            lines = [ln.strip() for ln in diff_text.splitlines() if ln.strip()]
            diff_terms = []
            for line in lines:
                clean = re.sub(r'^[-•*]\s*', '', line)
                clean = re.sub(r'^\d+[.)]\s*', '', clean)
                clean = clean.strip()
                if not clean:
                    continue
                term = clean.split('|')[0].strip()
                term = term.split(':')[0].strip()
                term = re.sub(r'\s+', ' ', term).strip(' -')
                if len(term) > 3:
                    diff_terms.append(term)

            for i, term in enumerate(diff_terms[:5]):
                if any(self._diagnoses_match(term, d['term']) for d in diagnoses):
                    continue
                score = max(0.70 - (i * 0.10), 0.32)
                diagnoses.append({'term': term, 'score': score})

        # CONFIDENCE
        confidence_text = self._extract_section(response, ['confidence'])
        confidence_source = confidence_text if confidence_text else response

        pct_match = re.search(r'(\d{1,3})\s*%', confidence_source)
        if pct_match:
            pct = min(max(int(pct_match.group(1)), 0), 95)
            confidence_score = pct / 100.0
        else:
            confidence_map = [
                ('moderate-high confidence', 0.72),
                ('low-moderate confidence', 0.45),
                ('high confidence', 0.85),
                ('moderate confidence', 0.58),
                ('low confidence', 0.32),
                ('moderate-high', 0.68),
                ('low-moderate', 0.42),
                ('moderate', 0.55),
                ('high', 0.80),
                ('low', 0.30),
            ]
            lower_source = confidence_source.lower()
            for indicator, score in confidence_map:
                if re.search(r'\b' + re.escape(indicator) + r'\b', lower_source):
                    confidence_score = score
                    break

        interpretation = self._interpret_confidence(confidence_score)

        # Safety-based confidence penalties
        response_lower = response.lower()
        if any(flag in response_lower for flag in ['red flag', 'urgent', 'life-threatening', 'emergency']):
            confidence_score = min(confidence_score, 0.45)
            interpretation = "Low-moderate confidence - Urgent evaluation required"

        if 'pattern' in response_lower and ('not match' in response_lower or 'mismatch' in response_lower):
            confidence_score = min(confidence_score, 0.40)
            interpretation = self._interpret_confidence(confidence_score)

        medications = self._extract_medications(response)
        recommendations = self._extract_recommendations(response)
        summary = self._extract_section(response, ['summary'])

        return {
            'diagnoses': diagnoses[:6],
            'active_diagnoses': [],
            'confidence_score': confidence_score,
            'interpretation': interpretation,
            'recommendations': recommendations,
            'medications': medications,
            'summary': summary,
            'doctor_actions': [],
        }
    
    def _extract_medications(self, response: str) -> List[Dict]:
        """Extract medication recommendations and map to model serializer fields"""
        medications = []
        med_text = self._extract_section(response, ['medications'])
        if not med_text:
            return medications

        lines = [line.strip() for line in med_text.split('\n') if line.strip()]
        for line in lines[:8]:
            lower_line = line.lower()
            if 'no empiric medication' in lower_line or 'no empiric medications' in lower_line:
                return []

            clean = re.sub(r'^[-•*\d]+[.\)]?\s*', '', line).strip()
            if not clean:
                continue

            if '|' in clean:
                parts = [p.strip() for p in clean.split('|')]
                if len(parts) < 4:
                    continue
                instruction_parts = []
                if len(parts) > 4 and parts[4]:
                    instruction_parts.append(f"Purpose: {parts[4]}")
                if len(parts) > 5 and parts[5]:
                    instruction_parts.append(f"Safety: {parts[5]}")

                medications.append({
                    'medication_name': parts[0],
                    'dosage': parts[1],
                    'frequency': parts[2],
                    'duration': parts[3],
                    'instructions': '; '.join(instruction_parts),
                })
                continue

            # Unstructured fallback: "<Medication> <dose> <frequency> ..."
            med_pattern = (
                r'([A-Z][a-zA-Z]+(?:[\s\-][A-Z]?[a-zA-Z]+)*(?:\s*\([A-Za-z]+\))?)\s+'
                r'(\d+(?:\.\d+)?\s*(?:mg|ml|mcg|g|units?|tablets?|capsules?|puffs?))\s+'
                r'([^\n,;]+)'
            )
            match = re.search(med_pattern, clean)
            if not match:
                continue

            medications.append({
                'medication_name': match.group(1).strip(),
                'dosage': match.group(2).strip(),
                'frequency': match.group(3).strip(),
                'duration': 'As clinically indicated',
                'instructions': '',
            })

        return medications
    
    def _extract_recommendations(self, response: str) -> List[str]:
        """Extract diagnostic workup recommendations"""
        rec_text = self._extract_section(response, ['workup'])
        if not rec_text:
            return []

        recs = re.findall(r'[-•*\d]+[.\)]\s*([^\n]+)', rec_text)
        if not recs:
            recs = [line.strip() for line in rec_text.split('\n') if line.strip()]

        recommendations = []
        for rec in recs:
            cleaned = re.sub(r'\s+', ' ', rec).strip(' -')
            if len(cleaned) < 8:
                continue
            recommendations.append(cleaned)
            if len(recommendations) >= 6:
                break
        return recommendations

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

    def _normalize_medication_fields(self, dosage: str, frequency: str, duration: str, instructions: str) -> Tuple[str, str, str, str]:
        dosage_value = str(dosage or '').strip()
        frequency_value = str(frequency or '').strip()
        duration_value = str(duration or '').strip()
        instructions_value = str(instructions or '').strip()

        dosage_is_frequency = self._looks_like_frequency(dosage_value) and not self._looks_like_dosage(dosage_value)
        frequency_is_dosage = self._looks_like_dosage(frequency_value) and not self._looks_like_frequency(frequency_value)
        if dosage_is_frequency and frequency_is_dosage:
            dosage_value, frequency_value = frequency_value, dosage_value

        if duration_value and not re.search(r'\b(?:day|days|week|weeks|month|months|year|years|as needed|prn)\b', duration_value.lower()):
            if len(duration_value.split()) >= 6:
                instructions_value = f"{instructions_value}; {duration_value}".strip('; ').strip()
                duration_value = 'Per clinical protocol'

        return dosage_value, frequency_value, duration_value, instructions_value

    def _normalize_medications(self, medications: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Normalize medication payload to backend serializer-compatible fields"""
        normalized = []
        seen = set()

        for med in medications:
            name = str(med.get('medication_name', '')).strip()
            if not name:
                continue
            if 'no empiric medication' in name.lower():
                continue

            key = re.sub(r'[^a-z0-9]+', '', name.lower())
            if not key or key in seen:
                continue
            seen.add(key)

            dosage = str(med.get('dosage', '')).strip() or 'Per guideline'
            frequency = str(med.get('frequency', '')).strip() or 'Per guideline'
            duration = str(med.get('duration', '')).strip() or 'Per clinical course'

            instructions = str(med.get('instructions', '')).strip()
            purpose = str(med.get('purpose', '')).strip()
            monitoring = str(med.get('monitoring', '')).strip()
            instruction_parts = []
            if instructions:
                instruction_parts.append(instructions)
            if purpose:
                instruction_parts.append(f"Purpose: {purpose}")
            if monitoring:
                instruction_parts.append(f"Safety: {monitoring}")

            normalized_instructions = '; '.join(instruction_parts)
            dosage, frequency, duration, normalized_instructions = self._normalize_medication_fields(
                dosage,
                frequency,
                duration,
                normalized_instructions,
            )

            normalized.append({
                'medication_name': name,
                'dosage': dosage,
                'frequency': frequency,
                'duration': duration,
                'instructions': normalized_instructions,
            })

            if len(normalized) >= 5:
                break

        return normalized

    def _build_fallback_medications(
        self,
        primary_diagnosis: str,
        red_flag_analysis: Dict[str, Any],
        case_text: str = '',
        active_diagnoses: List[str] = None,
    ) -> List[Dict[str, str]]:
        """Return conservative fallback medications with allergy-aware filtering."""
        active_diagnoses = active_diagnoses or []

        diagnosis_lower = primary_diagnosis.lower()
        combined_lower = f"{primary_diagnosis} {' '.join(active_diagnoses)} {case_text}".lower()

        has_penicillin_allergy = self._contains_any_marker(
            combined_lower,
            ['penicillin allergy', 'allergy to penicillin', 'penicillin caused hives', 'penicillin caused swelling'],
        )
        has_nsaid_allergy = self._contains_any_marker(
            combined_lower,
            ['nsaid allergy', 'allergy to nsaid', 'ibuprofen allergy', 'naproxen allergy'],
        )

        # In high-risk red-flag cases we generally avoid fallback medication generation,
        # except for supportive acute airway management.
        if red_flag_analysis.get('has_red_flags') and 'copd' not in diagnosis_lower:
            if not any('acute copd exacerbation' in str(dx).lower() for dx in active_diagnoses):
                return []

        alias_map = {
            'urinary tract infection': 'uti',
            'gastroesophageal reflux disease': 'gerd',
            'allergic rhinitis': 'allergic rhinitis',
            'community acquired pneumonia': 'pneumonia',
            'influenza-like illness': 'influenza-like illness',
            'viral upper respiratory infection': 'viral upper respiratory infection',
            'acute copd exacerbation': 'acute copd exacerbation',
        }
        protocol_keys = sorted(self.medication_protocols.keys(), key=len, reverse=True)

        protocol_key = ''
        for key in protocol_keys:
            if key in diagnosis_lower:
                protocol_key = key
                break

        if not protocol_key:
            for dx in active_diagnoses:
                dx_lower = str(dx).lower()
                for key in protocol_keys:
                    if key in dx_lower:
                        protocol_key = key
                        break
                if protocol_key:
                    break

        if not protocol_key:
            for alias, mapped_key in alias_map.items():
                if alias in diagnosis_lower:
                    protocol_key = mapped_key
                    break

        if not protocol_key:
            return []

        meds = [dict(item) for item in self.medication_protocols.get(protocol_key, [])]

        if has_penicillin_allergy:
            meds = [
                med for med in meds
                if not any(token in med.get('medication_name', '').lower() for token in ['penicillin', 'amoxicillin'])
            ]
            if protocol_key == 'pneumonia' and not meds:
                meds.append(
                    {
                        'medication_name': 'Doxycycline',
                        'dosage': '100 mg',
                        'frequency': 'PO every 12 hours',
                        'duration': '5 days',
                        'instructions': 'Non-penicillin option when bacterial respiratory infection is suspected and clinically appropriate.',
                    }
                )

        if has_nsaid_allergy:
            meds = [
                med for med in meds
                if not any(
                    token in med.get('medication_name', '').lower()
                    for token in ['ibuprofen', 'naproxen', 'diclofenac', 'ketorolac', 'nsaid']
                )
            ]

        # Keep fallback concise and conservative.
        return meds[:5]

    def _build_doctor_facing_reasoning(
        self, parsed: Dict[str, Any], red_flag_analysis: Dict[str, Any], hypotheses: Dict[str, Any]
    ) -> str:
        """Build consistent, concise, clinician-readable reasoning text"""
        lines = []

        if red_flag_analysis.get('has_red_flags'):
            flags = [f['flag'].replace('_', ' ') for f in red_flag_analysis.get('detected_flags', [])]
            lines.append(
                f"**URGENT ALERT**: {red_flag_analysis.get('urgency_level', 'HIGH')} priority red flags detected"
                f" ({', '.join(flags[:3])})."
            )

        if parsed.get('diagnoses'):
            lines.append(f"**PRIMARY DIAGNOSIS**: {parsed['diagnoses'][0]['term']}")
        else:
            lines.append("**PRIMARY DIAGNOSIS**: Undifferentiated syndrome - further workup required")

        active_diagnoses = parsed.get('active_diagnoses', [])
        if isinstance(active_diagnoses, list) and len(active_diagnoses) > 1:
            lines.append("**ACTIVE DIAGNOSES (MULTIMORBIDITY)**")
            for idx, diagnosis in enumerate(active_diagnoses[:5], 1):
                lines.append(f"{idx}. {diagnosis}")

        lines.append("**DIFFERENTIAL DIAGNOSES**")
        if parsed.get('diagnoses'):
            for idx, diag in enumerate(parsed['diagnoses'][:5], 1):
                score_pct = int(max(0.0, min(diag.get('score', 0.0), 0.99)) * 100)
                lines.append(f"{idx}. {diag['term']} ({score_pct}%)")
        else:
            for idx, cand in enumerate(hypotheses.get('candidates', [])[:4], 1):
                lines.append(f"{idx}. {cand['term']} ({int(cand['score'] * 100)}%)")

        confidence_pct = int(max(0.0, min(parsed.get('confidence_score', 0.0), 0.99)) * 100)
        lines.append(f"**CONFIDENCE**: {confidence_pct}% - {parsed.get('interpretation', 'Clinical correlation required')}")

        if parsed.get('recommendations'):
            lines.append("**RECOMMENDED WORKUP**")
            for rec in parsed['recommendations'][:6]:
                lines.append(f"- {rec}")

        if parsed.get('doctor_actions'):
            lines.append("**DOCTOR ACTION CHECKLIST**")
            for action in parsed['doctor_actions'][:5]:
                lines.append(f"- {action}")

        lines.append("**MEDICATION RECOMMENDATIONS**")
        if parsed.get('medications'):
            for med in parsed['medications'][:5]:
                instruction = med.get('instructions', '')
                if instruction:
                    lines.append(
                        f"- {med['medication_name']} | {med['dosage']} | {med['frequency']} | {med['duration']} | {instruction}"
                    )
                else:
                    lines.append(
                        f"- {med['medication_name']} | {med['dosage']} | {med['frequency']} | {med['duration']}"
                    )
        else:
            lines.append("- No empiric medications until further workup if diagnosis remains uncertain.")

        summary = parsed.get('summary', '').strip()
        if not summary:
            if red_flag_analysis.get('has_red_flags'):
                summary = "Urgent evaluation is required to rule out life-threatening etiologies."
            elif parsed.get('diagnoses'):
                summary = f"Most likely diagnosis is {parsed['diagnoses'][0]['term']}; complete recommended workup before definitive treatment."
            else:
                summary = "Diagnosis remains broad; prioritize targeted labs/imaging and re-assess."

        lines.append("**CLINICAL SUMMARY**")
        lines.append(summary)

        return '\n'.join(lines)
    
    def _extract_clinical_features(self, symptoms_text: str, clinical_notes: str) -> List[str]:
        """Extract positive clinical features (exclude negations) with improved matching"""
        
        combined_text = f"{symptoms_text} {clinical_notes}".lower()
        
        # Medical keywords with common variations included
        medical_keywords = {
            'fever': 'Fever',
            'febrile': 'Fever',
            'lagnat': 'Fever',
            'cough': 'Cough',
            'coughing': 'Cough',
            'ubo': 'Cough',
            'inuubo': 'Cough',
            'productive cough': 'Productive Cough',
            'yellow-green sputum': 'Purulent Sputum',
            'purulent sputum': 'Purulent Sputum',
            'hemoptysis': 'Hemoptysis',
            'coughing blood': 'Hemoptysis',
            'coughing up blood': 'Hemoptysis',
            'blood in sputum': 'Hemoptysis',
            'dyspnea': 'Dyspnea',
            'shortness of breath': 'Dyspnea',
            'difficulty breathing': 'Dyspnea',
            'breathlessness': 'Dyspnea',
            'shortness of breath on exertion': 'Dyspnea on Exertion',
            'exertional dyspnea': 'Dyspnea on Exertion',
            'chest pain': 'Chest Pain',
            'chest discomfort': 'Chest Pain',
            'chest pressure': 'Chest Pain',
            'wheezing': 'Wheezing',
            'wheeze': 'Wheezing',
            'crackles': 'Crackles',
            'rales': 'Crackles',
            'spo2': 'Low Oxygen Saturation',
            'fatigue': 'Fatigue',
            'tiredness': 'Fatigue',
            'exhaustion': 'Fatigue',
            'weakness': 'Weakness',
            'nausea': 'Nausea',
            'nauseous': 'Nausea',
            'vomiting': 'Vomiting',
            'vomit': 'Vomiting',
            'throwing up': 'Vomiting',
            'diarrhea': 'Diarrhea',
            'loose stools': 'Diarrhea',
            'watery stools': 'Diarrhea',
            'headache': 'Headache',
            'head pain': 'Headache',
            'masakit ulo': 'Headache',
            'dizziness': 'Dizziness',
            'dizzy': 'Dizziness',
            'lightheaded': 'Dizziness',
            'abdominal pain': 'Abdominal Pain',
            'stomach pain': 'Abdominal Pain',
            'belly pain': 'Abdominal Pain',
            'runny nose': 'Runny Nose',
            'rhinorrhea': 'Runny Nose',
            'nasal congestion': 'Nasal Congestion',
            'stuffy nose': 'Nasal Congestion',
            'sipon': 'Runny Nose',
            'nose bleed': 'Epistaxis',
            'nosebleed': 'Epistaxis',
            'nose bleeding': 'Epistaxis',
            'nasal bleeding': 'Epistaxis',
            'epistaxis': 'Epistaxis',
            'weight loss': 'Weight Loss',
            'losing weight': 'Weight Loss',
            'night sweats': 'Night Sweats',
            'nocturnal sweating': 'Night Sweats',
            'throat itching': 'Throat Irritation',
            'itchy throat': 'Throat Irritation',
            'sore throat': 'Sore Throat',
            'throat pain': 'Sore Throat',
            'swelling': 'Edema',
            'swollen': 'Edema',
            'edema': 'Edema',
            'puffiness': 'Edema',
            'bloating': 'Bloating',
            'constipation': 'Constipation',
            'cramping': 'Cramping',
            'cramps': 'Cramping',
            'malaise': 'Malaise',
            'palpitations': 'Palpitations',
            'heart racing': 'Palpitations',
            'rash': 'Rash',
            'skin rash': 'Rash',
            'joint pain': 'Joint Pain',
            'arthralgia': 'Joint Pain',
            'body aches': 'Body Aches',
            'myalgia': 'Body Aches',
            'muscle pain': 'Body Aches',
            'sakit ng katawan': 'Body Aches',
            'pananakit ng katawan': 'Body Aches',
            'depressed mood': 'Depressed Mood',
            'persistent depressed mood': 'Depressed Mood',
            'low mood': 'Depressed Mood',
            'anhedonia': 'Anhedonia',
            'diminished interest': 'Anhedonia',
            'loss of interest': 'Anhedonia',
            'insomnia': 'Insomnia',
            'early morning awakening': 'Insomnia',
            'psychomotor retardation': 'Psychomotor Retardation',
            'slowed speech': 'Psychomotor Retardation',
            'slowed movements': 'Psychomotor Retardation',
            'worthlessness': 'Worthlessness',
            'excessive guilt': 'Excessive Guilt',
            'difficulty concentrating': 'Poor Concentration',
            'indecisiveness': 'Poor Concentration',
            'suicidal ideation': 'Suicidal Ideation',
            'suicidal thoughts': 'Suicidal Ideation',
            'thoughts of death': 'Suicidal Ideation',
            'self harm': 'Suicidal Ideation',
            'self-harm': 'Suicidal Ideation',
            'precocious puberty': 'Precocious Puberty',
            'early puberty': 'Precocious Puberty',
            'premature puberty': 'Precocious Puberty',
            'cafe au lait spots': 'Cafe-au-lait Spots',
            'cafe-au-lait spots': 'Cafe-au-lait Spots',
            'cafe au lait': 'Cafe-au-lait Spots',
            'fibrous dysplasia': 'Fibrous Dysplasia',
            'polyostotic fibrous dysplasia': 'Fibrous Dysplasia',
            'monostotic fibrous dysplasia': 'Fibrous Dysplasia',
            'chills': 'Chills',
            'hypertension': 'Hypertension',
            'high blood pressure': 'Hypertension',
            'ankle swelling': 'Peripheral Edema',
            'peripheral edema': 'Peripheral Edema',
            'polyuria': 'Polyuria',
            'polydipsia': 'Polydipsia',
            'hyperglycemia': 'Hyperglycemia',
            'high blood sugar': 'Hyperglycemia',
            'hba1c': 'Elevated HbA1c',
            'elevated hba1c': 'Elevated HbA1c',
            'renal impairment': 'Renal Impairment',
            'reduced egfr': 'Renal Impairment',
            'elevated creatinine': 'Elevated Creatinine',
            'gout': 'Gout',
            'acute gout flare': 'Acute Gout Flare',
            'podagra': 'Acute Gout Flare',
            'great toe pain': 'Great Toe Pain',
            'metatarsophalangeal': 'Great Toe Joint Inflammation',
            'uric acid': 'Hyperuricemia',
            'hyperuricemia': 'Hyperuricemia',
            'poor adherence': 'Poor Medication Adherence',
            'nonadherence': 'Poor Medication Adherence',
            'irregular rhythm': 'Irregular Rhythm',
            'premature atrial contractions': 'Premature Atrial Contractions',
        }
        
        found_keywords = []
        found_display_names = set()  # Track display names to avoid duplicates
        
        for keyword, display_name in medical_keywords.items():
            # Use shared helper method for negation logic
            if self._is_present_and_not_negated(keyword, combined_text):
                if display_name not in found_display_names:
                    found_keywords.append(display_name)
                    found_display_names.add(display_name)
        
        return found_keywords[:12]
    
    def _interpret_confidence(self, score: float) -> str:
        """Interpret confidence score"""
        if score > 0.78:
            return "High confidence - Strong clinical and objective evidence"
        elif score > 0.65:
            return "Moderate-high confidence - Primary diagnosis likely"
        elif score > 0.50:
            return "Moderate confidence - Consider differential carefully"
        elif score > 0.38:
            return "Low-moderate confidence - Requires further workup"
        else:
            return "Low confidence - Rule-out diagnosis or urgent evaluation needed"
    
    def _build_error_response(self, error_msg: str) -> Dict[str, Any]:
        """Build standardized error response"""
        return {
            'error': error_msg,
            'confidence_score': 0.0,
            'suggested_diagnoses': [],
            'keywords': [],
            'interpretation': 'Analysis failed',
            'clinical_reasoning': error_msg,
            'raw_clinical_reasoning': error_msg,
            'summary': '',
            'recommendations': [],
            'medications': [],
            'active_diagnoses': [],
            'red_flag_analysis': {'has_red_flags': False, 'urgency_level': 'UNKNOWN', 'detected_flags': []}
        }


# Initialize service
print("=" * 70)
print("Med42-v3 Production Clinical Service")
print("=" * 70)
print("Safety Features:")
print("  [OK] Red flag detection (hemoptysis, chest pain, altered MS, etc.)")
print("  [OK] Symptom pattern validation (prevents keyword-only errors)")
print("  [OK] Clinical decision rules (TB, bleeding disorders, etc.)")
print("  [OK] Medication safety checks")
print("  [OK] Confidence calibration with pattern validation")
print("=" * 70)

try:
    med42_service = Med42ServiceCloud(model_size="8B")
    print("Service ready")
except ValueError as e:
    print(f"Failed: {e}")
    print("Set HF_TOKEN environment variable")
    med42_service = None
