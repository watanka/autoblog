
import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.core.interfaces import DataStorage


class JsonFileStorage(DataStorage):
    """JSON 파일을 사용한 데이터 스토리지 구현"""
    
    def __init__(self, base_dir: str):
        """
        초기화합니다.
        
        Args:
            base_dir (str): 데이터 저장 기본 디렉토리
        """
        self.base_dir = base_dir
        self.logger = logging.getLogger('autoblog.storage')
        
        # 데이터 디렉토리 생성
        os.makedirs(f"{self.base_dir}/trends", exist_ok=True)
        os.makedirs(f"{self.base_dir}/contents", exist_ok=True)
        os.makedirs(f"{self.base_dir}/results", exist_ok=True)
        os.makedirs(f"{self.base_dir}/metadata", exist_ok=True)
    
    def save_data(self, data: Any, path: str, job_id: Optional[str] = None) -> str:
        """
        데이터를 JSON 파일로 저장합니다.
        
        Args:
            data (Any): 저장할 데이터
            path (str): 저장 경로 템플릿
            job_id (Optional[str]): 작업 ID
            
        Returns:
            str: 데이터가 저장된 실제 경로
        """
        # 작업 ID가 있으면 파일 경로에 포함
        if job_id and '{job_id}' in path:
            final_path = path.format(job_id=job_id)
        elif job_id:
            # 작업 ID가 있지만 템플릿에 없는 경우, 파일 이름에 추가
            base, ext = os.path.splitext(path)
            final_path = f"{base}_{job_id}{ext}"
        else:
            # 작업 ID가 없으면 타임스탬프 사용
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base, ext = os.path.splitext(path)
            final_path = f"{base}_{timestamp}{ext}"
        
        full_path = os.path.join(self.base_dir, final_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.debug(f"데이터 저장 완료: {full_path}")
        return full_path
    
    def load_data(self, path: str, job_id: Optional[str] = None) -> Any:
        """
        JSON 파일에서 데이터를 로드합니다.
        
        Args:
            path (str): 로드할 데이터 경로 템플릿
            job_id (Optional[str]): 작업 ID
            
        Returns:
            Any: 로드된 데이터
            
        Raises:
            FileNotFoundError: 지정된 경로에 파일이 없는 경우
        """
        try:
            # 작업 ID가 있는 경우
            if job_id and '{job_id}' in path:
                final_path = path.format(job_id=job_id)
                full_path = os.path.join(self.base_dir, final_path)
                
                if not os.path.exists(full_path):
                    raise FileNotFoundError(f"지정된 작업 ID의 파일이 없습니다: {full_path}")
                
                with open(full_path, 'r', encoding='utf-8') as f:
                    self.logger.debug(f"데이터 로드 완료: {full_path}")
                    return json.load(f)
            
            # 작업 ID가 없는 경우, 최신 메타데이터 확인
            if job_id is None:
                metadata = self.find_latest_job('completed')
                if metadata and 'files' in metadata:
                    # 파일 경로에서 파일 유형 확인 (trends, contents, results)
                    file_type = path.split('/')[0]  # 예: "trends/latest.json" -> "trends"
                    
                    if file_type in metadata['files'] and metadata['files'][file_type]:
                        file_path = metadata['files'][file_type]
                        if os.path.isabs(file_path):
                            full_path = file_path
                        else:
                            # 상대 경로인 경우, base_dir과 결합
                            full_path = os.path.join(self.base_dir, file_path) 
                            if not file_path.startswith(file_type):
                                # 파일 유형으로 시작하지 않는 경우 (상대 경로가 아닌 경우)
                                full_path = os.path.join(self.base_dir, file_type, os.path.basename(file_path))
                        
                        if os.path.exists(full_path):
                            with open(full_path, 'r', encoding='utf-8') as f:
                                self.logger.debug(f"메타데이터에서 찾은 데이터 로드 완료: {full_path}")
                                return json.load(f)
            
            # 그 외의 경우, 기본 경로에서 최신 파일 찾기
            dir_path = os.path.join(self.base_dir, os.path.dirname(path))
            if not os.path.exists(dir_path):
                raise FileNotFoundError(f"지정된 디렉토리가 없습니다: {dir_path}")
                
            files = [f for f in os.listdir(dir_path) if f.endswith('.json')]
            if not files:
                raise FileNotFoundError(f"로드할 파일이 없습니다: {dir_path}")
                
            # 수정 시간 기준으로 최신 파일 선택
            latest_file = max(files, key=lambda x: os.path.getmtime(os.path.join(dir_path, x)))
            full_path = os.path.join(dir_path, latest_file)
                
            with open(full_path, 'r', encoding='utf-8') as f:
                self.logger.debug(f"최신 파일 로드 완료: {full_path}")
                return json.load(f)
                
        except Exception as e:
            self.logger.error(f"데이터 로드 중 오류 발생: {str(e)}")
            raise
    
    def create_metadata(self, job_id: str, metadata: Dict[str, Any]) -> str:
        """
        작업 메타데이터 파일을 생성합니다.
        
        Args:
            job_id (str): 작업 ID
            metadata (Dict[str, Any]): 메타데이터
            
        Returns:
            str: 메타데이터 파일 경로
        """
        metadata_path = f"metadata/job_{job_id}.json"
        full_path = self.save_data(metadata, metadata_path)
        self.logger.info(f"작업 메타데이터 생성 완료: {full_path}")
        return full_path
    
    def update_metadata(self, job_id: str, key: str, value: Any) -> bool:
        """
        작업 메타데이터를 업데이트합니다.
        
        Args:
            job_id (str): 작업 ID
            key (str): 업데이트할 키 (점으로 구분된 중첩 키 지원, 예: "files.trends")
            value (Any): 설정할 값
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            metadata_path = os.path.join(self.base_dir, f"metadata/job_{job_id}.json")
            
            if not os.path.exists(metadata_path):
                self.logger.error(f"메타데이터 파일이 없습니다: {metadata_path}")
                return False
            
            # 메타데이터 로드
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # 중첩 키 처리 (예: "files.trends")
            keys = key.split('.')
            target = metadata
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            
            # 값 설정
            target[keys[-1]] = value
            
            # 업데이트 시간 추가
            metadata['updated_at'] = datetime.now().isoformat()
            
            # 메타데이터 저장
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                
            self.logger.debug(f"메타데이터 업데이트 완료: {metadata_path}, 키: {key}")
            return True
            
        except Exception as e:
            self.logger.error(f"메타데이터 업데이트 중 오류 발생: {str(e)}")
            return False
    
    def find_latest_job(self, status: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        가장 최근 작업의 메타데이터를 찾습니다.
        
        Args:
            status (Optional[str]): 찾을 작업 상태 (None이면 모든 상태)
            
        Returns:
            Optional[Dict[str, Any]]: 메타데이터 딕셔너리, 없으면 None
        """
        try:
            metadata_dir = os.path.join(self.base_dir, "metadata")
            if not os.path.exists(metadata_dir):
                return None
                
            files = [f for f in os.listdir(metadata_dir) if f.startswith('job_') and f.endswith('.json')]
            if not files:
                return None
                
            # 파일 수정 시간 기준으로 정렬
            latest_files = sorted(
                files, 
                key=lambda x: os.path.getmtime(os.path.join(metadata_dir, x)),
                reverse=True
            )
            
            # 상태가 지정된 경우, 해당 상태의 작업 찾기
            if status:
                for file in latest_files:
                    file_path = os.path.join(metadata_dir, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    if metadata.get('status') == status:
                        self.logger.debug(f"상태 '{status}'의 최신 작업 찾음: {file}")
                        return metadata
            
            # 상태가 지정되지 않았거나, 지정된 상태의 작업이 없는 경우, 가장 최신 작업 반환
            file_path = os.path.join(metadata_dir, latest_files[0])
            with open(file_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                
            self.logger.debug(f"최신 작업 찾음: {latest_files[0]}")
            return metadata
                
        except Exception as e:
            self.logger.error(f"최신 작업 메타데이터 찾기 중 오류 발생: {str(e)}")
            return None
