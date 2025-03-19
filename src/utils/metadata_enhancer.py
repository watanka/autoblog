import os
import json
import time
from datetime import datetime

# 지원하는 LLM 서비스 목록
SUPPORTED_LLM_SERVICES = ['openai', 'anthropic', 'google', 'cohere', 'mistral', 'custom']

# LLM 서비스별 비용 계수 (1000 토큰당 USD 기준, 예상치)
LLM_COST_FACTORS = {
    'openai': 0.002,  # GPT-3.5 기준
    'anthropic': 0.0025,  # Claude 기준
    'google': 0.0005,  # Gemini Pro 기준
    'cohere': 0.0015,  # 예상치
    'mistral': 0.0008,  # Mistral 7B 기준
    'custom': 0.001  # 기본값
}

def update_job_metadata(job_id, metadata_updates):
    """
    작업 메타데이터에 모니터링 정보를 추가하는 함수
    
    Args:
        job_id (str): 업데이트할 작업의, ID
        metadata_updates (dict): 추가할 메타데이터 정보
    
    Returns:
        bool: 성공 여부
    """
    try:
        metadata_path = os.path.join('data', 'metadata', f'job_{job_id}.json')
        
        # 기존 메타데이터 읽기
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = {
                'job_id': job_id,
                'timestamp': datetime.now().isoformat(),
                'status': 'unknown'
            }
        
        # 모니터링 정보 업데이트
        metadata.update(metadata_updates)
        
        # 타임스탬프 업데이트
        if 'updated_at' not in metadata_updates:
            metadata['updated_at'] = datetime.now().isoformat()
        
        # 메타데이터 저장
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
            
        return True
    
    except Exception as e:
        print(f"메타데이터 업데이트 중 오류: {e}")
        return False

def track_llm_usage(job_id, service_name, tokens_used=0, requests_made=1, model_name=None):
    """
    LLM API 사용량을 추적하여 메타데이터에 저장
    
    Args:
        job_id (str): 작업 ID
        service_name (str): LLM 서비스 이름 (예: 'openai', 'anthropic', 'google')
        tokens_used (int): 사용된 토큰 수
        requests_made (int): API 요청 횟수
        model_name (str, optional): 사용된 모델 이름 (예: 'gpt-3.5-turbo', 'claude-2')
    """
    # 서비스 이름 정규화
    service_name = service_name.lower()
    
    # 알 수 없는 서비스는 'custom'으로 처리
    if service_name not in SUPPORTED_LLM_SERVICES:
        service_name = 'custom'
    
    # 비용 계산
    cost_factor = LLM_COST_FACTORS.get(service_name, 0.001)
    cost = (tokens_used / 1000) * cost_factor
    
    updates = {
        'llm_service': service_name,
        f'{service_name}_tokens': tokens_used,
        f'{service_name}_requests': requests_made,
        f'{service_name}_cost': cost
    }
    
    # 모델 이름이 제공된 경우 추가
    if model_name:
        updates[f'{service_name}_model'] = model_name
    
    update_job_metadata(job_id, updates)

def track_api_usage(job_id, api_name, tokens_used=0, requests_made=0):
    """
    API 사용량을 추적하여 메타데이터에 저장 (이전 버전과의 호환성 유지)
    
    Args:
        job_id (str): 작업 ID
        api_name (str): API 이름 (예: 'openai', 'news')
        tokens_used (int): 사용된 토큰 수 (OpenAI API 등)
        requests_made (int): 요청 횟수
    """
    if api_name.lower() == 'openai':
        track_llm_usage(job_id, 'openai', tokens_used, requests_made)
    elif api_name.lower() in SUPPORTED_LLM_SERVICES:
        track_llm_usage(job_id, api_name.lower(), tokens_used, requests_made)
    elif api_name.lower() == 'news':
        updates = {'news_api_requests': requests_made}
        update_job_metadata(job_id, updates)
    else:
        # 기타 API는 필요시 추가
        updates = {f'{api_name.lower()}_requests': requests_made}
        update_job_metadata(job_id, updates)

def track_performance(job_id, operation, start_time=None, end_time=None, duration=None):
    """
    작업 성능 정보를 추적하여 메타데이터에 저장
    
    Args:
        job_id (str): 작업 ID
        operation (str): 작업 유형 (예: 'content_generation', 'publishing')
        start_time (float, optional): 시작 시간 (time.time() 값)
        end_time (float, optional): 종료 시간 (time.time() 값)
        duration (float, optional): 직접 계산된 소요 시간 (초)
    """
    if duration is None and start_time is not None and end_time is not None:
        duration = end_time - start_time
    
    if duration is not None:
        updates = {
            f'{operation}_time': duration,
            f'{operation}_timestamp': datetime.now().isoformat()
        }
        update_job_metadata(job_id, updates)

def update_job_status(job_id, status, error_message=None):
    """
    작업 상태를 업데이트
    
    Args:
        job_id (str): 작업 ID
        status (str): 작업 상태 ('pending', 'in_progress', 'success', 'failed')
        error_message (str, optional): 오류 메시지 (상태가 'failed'인 경우)
    """
    updates = {'status': status}
    
    if status == 'failed' and error_message:
        updates['error'] = error_message
    
    update_job_metadata(job_id, updates) 