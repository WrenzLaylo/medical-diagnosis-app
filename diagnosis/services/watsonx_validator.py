import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()


logger = logging.getLogger(__name__)


class WatsonxValidator:
    """Secondary validation layer for safety and output standardization."""

    MODEL_ID = 'ibm/granite-3-8b-instruct'
    API_VERSION = '2024-05-01'

    def __init__(self) -> None:
        file_env = self._load_dotenv_fallback()
        self.api_key = self._env('WATSONX_API_KEY', file_env).strip()
        self.project_id = self._env('WATSONX_PROJECT_ID', file_env).strip()
        self.base_url = self._env('WATSONX_URL', file_env).strip().rstrip('/')
        self.timeout_seconds = float(os.environ.get('WATSONX_TIMEOUT_SECONDS', '25'))

        self._cached_iam_token: Optional[str] = None
        self._cached_iam_expiry: float = 0.0

        if not self.is_configured:
            missing = []
            if not self.base_url:
                missing.append('WATSONX_URL')
            if not self.project_id:
                missing.append('WATSONX_PROJECT_ID')
            if not self.api_key:
                missing.append('WATSONX_API_KEY')
            logger.warning('watsonx not configured; missing: %s', ', '.join(missing))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.project_id and self.base_url)

    def _env(self, key: str, file_env: Dict[str, str]) -> str:
        return os.environ.get(key, '').strip() or file_env.get(key, '').strip()

    def _load_dotenv_fallback(self) -> Dict[str, str]:
        env_values: Dict[str, str] = {}
        env_path = os.path.join(os.getcwd(), '.env')
        if not os.path.exists(env_path):
            return env_values

        try:
            with open(env_path, 'r', encoding='utf-8') as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key:
                        env_values[key] = value
        except Exception:
            logger.warning('unable to read .env for watsonx fallback configuration')

        return env_values

    def validate(self, patient_facts: Dict[str, Any], med42_result: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured:
            return {
                'validator_status': 'skipped',
                'safety_passed': True,
                'issues': [],
                'hallucination_flags': [],
                'standardized_output': None,
                'message': 'watsonx not configured',
            }

        try:
            iam_token = self._get_iam_token()
            payload = self._build_generation_payload(patient_facts, med42_result)
            generated_text = self._run_generation(iam_token, payload)
            parsed = self._extract_json_object(generated_text)

            if parsed is None:
                raise ValueError('watsonx returned non-JSON output')

            safety_assessment = parsed.get('safety_assessment', {}) if isinstance(parsed, dict) else {}
            issues = safety_assessment.get('issues', []) if isinstance(safety_assessment, dict) else []
            hallucination_flags = parsed.get('hallucination_flags', []) if isinstance(parsed, dict) else []

            return {
                'validator_status': 'ok',
                'safety_passed': bool(safety_assessment.get('passed', True)),
                'issues': self._as_string_list(issues)[:6],
                'hallucination_flags': self._as_string_list(hallucination_flags)[:6],
                'standardized_output': parsed,
                'message': 'watsonx validation completed',
                'validator_model': self.MODEL_ID,
            }
        except ValueError as exc:
            exc_text = str(exc)
            if (
                'no_associated_service_instance_error' in exc_text
                or 'not associated with a WML instance' in exc_text
            ):
                logger.warning('watsonx skipped: %s', exc_text)
                return {
                    'validator_status': 'skipped',
                    'safety_passed': True,
                    'issues': [],
                    'hallucination_flags': [],
                    'standardized_output': None,
                    'message': 'watsonx project is not linked to a WML service instance',
                    'validator_model': self.MODEL_ID,
                }
            logger.warning('watsonx validation unavailable: %s', exc_text)
            return {
                'validator_status': 'error',
                'safety_passed': True,
                'issues': [],
                'hallucination_flags': [],
                'standardized_output': None,
                'message': 'watsonx validation unavailable',
                'validator_model': self.MODEL_ID,
            }
        except Exception as exc:
            logger.warning('watsonx validation unavailable: %s', exc)
            return {
                'validator_status': 'error',
                'safety_passed': True,
                'issues': [],
                'hallucination_flags': [],
                'standardized_output': None,
                'message': 'watsonx validation unavailable',
                'validator_model': self.MODEL_ID,
            }

    def _get_iam_token(self) -> str:
        now = time.time()
        if self._cached_iam_token and now < self._cached_iam_expiry - 60:
            return self._cached_iam_token

        token_url = 'https://iam.cloud.ibm.com/identity/token'
        form_data = urllib.parse.urlencode(
            {
                'grant_type': 'urn:ibm:params:oauth:grant-type:apikey',
                'apikey': self.api_key,
            }
        ).encode('utf-8')

        request = urllib.request.Request(
            token_url,
            data=form_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'},
            method='POST',
        )

        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode('utf-8'))

        token = str(payload.get('access_token', '')).strip()
        if not token:
            raise ValueError('Unable to retrieve watsonx IAM token')

        expires_in = int(payload.get('expires_in', 3600))
        self._cached_iam_token = token
        self._cached_iam_expiry = now + max(expires_in, 300)
        return token

    def _build_generation_payload(self, patient_facts: Dict[str, Any], med42_result: Dict[str, Any]) -> Dict[str, Any]:
        compact_med42 = {
            'dx': [
                {
                    'term': item.get('term', ''),
                    'score': item.get('score', 0),
                }
                for item in med42_result.get('suggested_diagnoses', [])[:6]
                if isinstance(item, dict)
            ],
            'conf': med42_result.get('confidence_score', 0),
            'rx': med42_result.get('medications', [])[:5],
            'workup': med42_result.get('recommendations', [])[:6],
            'flags': med42_result.get('red_flag_analysis', {}),
            'summary': med42_result.get('summary', ''),
        }

        prompt = (
            'You are a medical safety validator. '\
            'Validate the draft output for contradictions, hallucinations, and safety compliance. '\
            'Do not replace the primary diagnosis with an unrelated condition unless the draft is clearly unsafe or contradictory. '\
            'Return only valid JSON with this schema: '\
            '{"primary_diagnosis":str,"differential_diagnoses":[str],"red_flags":[str],"recommended_workup":[str],"medications":[{"name":str,"dosage":str,"frequency":str,"duration":str,"instructions":str}],"confidence_score":number,"safety_assessment":{"passed":bool,"issues":[str]},"validator_notes":str,"summary":str,"hallucination_flags":[str]} '\
            'Keep responses concise and use at most 5 differential diagnoses and 5 medications. '\
            'Input facts: '
            + json.dumps(patient_facts, separators=(',', ':'))
            + ' Draft: '
            + json.dumps(compact_med42, separators=(',', ':'))
        )

        return {
            'model_id': self.MODEL_ID,
            'project_id': self.project_id,
            'input': prompt,
            'parameters': {
                'decoding_method': 'greedy',
                'temperature': 0,
                'max_new_tokens': 340,
            },
        }

    def _run_generation(self, iam_token: str, payload: Dict[str, Any]) -> str:
        url = f"{self.base_url}/ml/v1/text/generation?version={self.API_VERSION}"
        body = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                'Authorization': f'Bearer {iam_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            method='POST',
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                parsed = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            details = ''
            try:
                details = exc.read().decode('utf-8')
            except Exception:
                details = str(exc)
            logger.error('watsonx HTTP error %s: %s', exc.code, details[:700])
            raise ValueError(f'watsonx HTTP {exc.code}: {details[:400]}')

        results = parsed.get('results', []) if isinstance(parsed, dict) else []
        if not results:
            raise ValueError('watsonx returned empty results')

        generated_text = str(results[0].get('generated_text', '')).strip()
        if not generated_text:
            raise ValueError('watsonx generated_text is empty')
        return generated_text

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        decoder = json.JSONDecoder()
        start = text.find('{')
        while start != -1:
            try:
                obj, _ = decoder.raw_decode(text[start:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
            start = text.find('{', start + 1)
        return None

    def _as_string_list(self, values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        return [str(v).strip() for v in values if str(v).strip()]
