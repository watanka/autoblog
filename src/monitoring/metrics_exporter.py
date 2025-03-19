import os
import json
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import glob

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/metrics_exporter_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger('autoblog_metrics')

# 지원하는 LLM 서비스 목록
SUPPORTED_LLM_SERVICES = ['openai', 'anthropic', 'google', 'cohere', 'mistral', 'custom']

class AutoBlogMetrics:
    """AutoBlog 메트릭 수집 클래스"""
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.metrics = {
            # 시스템 상태 메트릭
            "autoblog_system_up": 1,
            
            # 작업 메트릭
            "autoblog_total_jobs": 0,
            "autoblog_successful_jobs": 0,
            "autoblog_failed_jobs": 0,
            "autoblog_pending_jobs": 0,
            
            # 데이터 메트릭
            "autoblog_trend_data_size_bytes": 0,
            "autoblog_content_data_size_bytes": 0,
            "autoblog_result_data_size_bytes": 0,
            "autoblog_metadata_size_bytes": 0,
            "autoblog_total_data_size_bytes": 0,
            
            # API 사용량 메트릭 (뉴스 API)
            "autoblog_news_api_requests": 0,
            
            # 총 비용 메트릭
            "autoblog_total_llm_cost_usd": 0,
        }
        
        # 각 LLM 서비스별 메트릭 초기화
        for service in SUPPORTED_LLM_SERVICES:
            self.metrics[f"autoblog_{service}_tokens_used"] = 0
            self.metrics[f"autoblog_{service}_cost_usd"] = 0
            self.metrics[f"autoblog_{service}_requests"] = 0
            
        # 성능 메트릭
        self.metrics["autoblog_avg_content_generation_time_seconds"] = 0
        self.metrics["autoblog_avg_publishing_time_seconds"] = 0
        
        # 마지막 업데이트 시간
        self.metrics["autoblog_last_metrics_update_timestamp"] = int(time.time())
        
        # LLM 서비스별 비용 계수 (1000 토큰당 USD 기준, 예상치)
        self.llm_cost_factors = {
            'openai': 0.002,  # GPT-3.5 기준
            'anthropic': 0.0025,  # Claude 기준
            'google': 0.0005,  # Gemini Pro 기준
            'cohere': 0.0015,  # 예상치
            'mistral': 0.0008,  # Mistral 7B 기준
            'custom': 0.001  # 기본값
        }
        
    def collect_metrics(self):
        """모든 메트릭 수집"""
        try:
            # 작업 메트릭 수집
            self._collect_job_metrics()
            
            # 데이터 크기 메트릭 수집
            self._collect_data_size_metrics()
            
            # 총 LLM 비용 계산
            total_cost = 0
            for service in SUPPORTED_LLM_SERVICES:
                total_cost += self.metrics[f"autoblog_{service}_cost_usd"]
            self.metrics["autoblog_total_llm_cost_usd"] = total_cost
            
            # 마지막 업데이트 시간 설정
            self.metrics["autoblog_last_metrics_update_timestamp"] = int(time.time())
            
            logger.info("메트릭 수집 완료")
            
        except Exception as e:
            logger.error(f"메트릭 수집 중 오류 발생: {e}")
            # 시스템 상태를 오류로 설정
            self.metrics["autoblog_system_up"] = 0
    
    def _collect_job_metrics(self):
        """작업 관련 메트릭 수집"""
        try:
            metadata_dir = os.path.join(self.data_dir, "metadata")
            if not os.path.exists(metadata_dir):
                logger.warning(f"메타데이터 디렉터리가 존재하지 않음: {metadata_dir}")
                return
                
            total_jobs = 0
            successful_jobs = 0
            failed_jobs = 0
            pending_jobs = 0
            
            # API 사용량 초기화
            news_api_requests = 0
            
            # LLM 서비스별 사용량 초기화
            llm_tokens = {service: 0 for service in SUPPORTED_LLM_SERVICES}
            llm_requests = {service: 0 for service in SUPPORTED_LLM_SERVICES}
            llm_costs = {service: 0.0 for service in SUPPORTED_LLM_SERVICES}
            
            # 성능 측정 초기화
            content_gen_times = []
            publishing_times = []
            
            # 메타데이터 파일 분석
            for filename in os.listdir(metadata_dir):
                if filename.endswith('.json'):
                    try:
                        with open(os.path.join(metadata_dir, filename), 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            
                            total_jobs += 1
                            
                            # 작업 상태에 따른 카운트
                            status = metadata.get('status', 'unknown')
                            if status == 'success':
                                successful_jobs += 1
                            elif status == 'failed':
                                failed_jobs += 1
                            elif status in ['pending', 'in_progress']:
                                pending_jobs += 1
                            
                            # 뉴스 API 사용량 추적
                            if 'news_api_requests' in metadata:
                                news_api_requests += metadata.get('news_api_requests', 0)
                            
                            # LLM 서비스 사용량 추적
                            llm_service = metadata.get('llm_service', 'openai').lower()
                            
                            # 알 수 없는 LLM 서비스는 'custom'으로 처리
                            if llm_service not in SUPPORTED_LLM_SERVICES:
                                llm_service = 'custom'
                                
                            if f'{llm_service}_tokens' in metadata:
                                tokens = metadata.get(f'{llm_service}_tokens', 0)
                                llm_tokens[llm_service] += tokens
                                
                                # 비용 계산
                                cost_factor = self.llm_cost_factors.get(llm_service, 0.001)
                                cost = (tokens / 1000) * cost_factor
                                llm_costs[llm_service] += cost
                                
                            # API 요청 횟수 추적
                            if f'{llm_service}_requests' in metadata:
                                llm_requests[llm_service] += metadata.get(f'{llm_service}_requests', 0)
                            elif 'llm_requests' in metadata:  # 이전 버전 호환성
                                llm_requests[llm_service] += metadata.get('llm_requests', 0)
                            else:
                                # 요청 횟수가 명시되지 않았으면 최소 1회로 가정
                                llm_requests[llm_service] += 1
                            
                            # 성능 측정 (메타데이터에 있다고 가정)
                            if 'content_generation_time' in metadata:
                                content_gen_times.append(metadata.get('content_generation_time', 0))
                            if 'publishing_time' in metadata:
                                publishing_times.append(metadata.get('publishing_time', 0))
                    
                    except Exception as e:
                        logger.error(f"메타데이터 파일 처리 중 오류: {filename}, {e}")
            
            # 메트릭 업데이트
            self.metrics["autoblog_total_jobs"] = total_jobs
            self.metrics["autoblog_successful_jobs"] = successful_jobs
            self.metrics["autoblog_failed_jobs"] = failed_jobs
            self.metrics["autoblog_pending_jobs"] = pending_jobs
            self.metrics["autoblog_news_api_requests"] = news_api_requests
            
            # LLM 서비스별 메트릭 업데이트
            for service in SUPPORTED_LLM_SERVICES:
                self.metrics[f"autoblog_{service}_tokens_used"] = llm_tokens[service]
                self.metrics[f"autoblog_{service}_cost_usd"] = llm_costs[service]
                self.metrics[f"autoblog_{service}_requests"] = llm_requests[service]
            
            # 성능 메트릭 계산
            if content_gen_times:
                self.metrics["autoblog_avg_content_generation_time_seconds"] = sum(content_gen_times) / len(content_gen_times)
            if publishing_times:
                self.metrics["autoblog_avg_publishing_time_seconds"] = sum(publishing_times) / len(publishing_times)
                
            logger.info(f"작업 메트릭 수집 완료: 총 {total_jobs}개 작업, 성공 {successful_jobs}개, 실패 {failed_jobs}개, 대기 {pending_jobs}개")
        
        except Exception as e:
            logger.error(f"작업 메트릭 수집 중 오류: {e}")
    
    def _collect_data_size_metrics(self):
        """데이터 크기 관련 메트릭 수집"""
        try:
            # 데이터 유형 및 경로
            data_types = {
                "trend": os.path.join(self.data_dir, "trends", "*.json"),
                "content": os.path.join(self.data_dir, "contents", "*.json"),
                "result": os.path.join(self.data_dir, "results", "*.json"),
                "metadata": os.path.join(self.data_dir, "metadata", "*.json")
            }
            
            total_size = 0
            
            # 각 데이터 유형별 크기 계산
            for data_type, pattern in data_types.items():
                size = 0
                for file_path in glob.glob(pattern):
                    if os.path.exists(file_path):
                        size += os.path.getsize(file_path)
                
                metric_key = f"autoblog_{data_type}_data_size_bytes"
                self.metrics[metric_key] = size
                total_size += size
            
            self.metrics["autoblog_total_data_size_bytes"] = total_size
            logger.info(f"데이터 크기 메트릭 수집 완료: 총 {total_size} 바이트")
        
        except Exception as e:
            logger.error(f"데이터 크기 메트릭 수집 중 오류: {e}")
    
    def format_prometheus(self):
        """Prometheus 형식으로 메트릭 포맷팅"""
        prometheus_lines = []
        
        # 기본 메트릭 유형 및 설명
        metric_types = {
            "autoblog_system_up": "# HELP autoblog_system_up 시스템 가용성 (1=실행 중, 0=오류)\n# TYPE autoblog_system_up gauge",
            "autoblog_total_jobs": "# HELP autoblog_total_jobs 총 작업 수\n# TYPE autoblog_total_jobs counter",
            "autoblog_successful_jobs": "# HELP autoblog_successful_jobs 성공한 작업 수\n# TYPE autoblog_successful_jobs counter",
            "autoblog_failed_jobs": "# HELP autoblog_failed_jobs 실패한 작업 수\n# TYPE autoblog_failed_jobs counter",
            "autoblog_pending_jobs": "# HELP autoblog_pending_jobs 대기 중인 작업 수\n# TYPE autoblog_pending_jobs gauge",
            "autoblog_trend_data_size_bytes": "# HELP autoblog_trend_data_size_bytes 트렌드 데이터 크기 (바이트)\n# TYPE autoblog_trend_data_size_bytes gauge",
            "autoblog_content_data_size_bytes": "# HELP autoblog_content_data_size_bytes 콘텐츠 데이터 크기 (바이트)\n# TYPE autoblog_content_data_size_bytes gauge",
            "autoblog_result_data_size_bytes": "# HELP autoblog_result_data_size_bytes 결과 데이터 크기 (바이트)\n# TYPE autoblog_result_data_size_bytes gauge",
            "autoblog_metadata_size_bytes": "# HELP autoblog_metadata_size_bytes 메타데이터 크기 (바이트)\n# TYPE autoblog_metadata_size_bytes gauge",
            "autoblog_total_data_size_bytes": "# HELP autoblog_total_data_size_bytes 총 데이터 크기 (바이트)\n# TYPE autoblog_total_data_size_bytes gauge",
            "autoblog_news_api_requests": "# HELP autoblog_news_api_requests 뉴스 API 요청 횟수\n# TYPE autoblog_news_api_requests counter",
            "autoblog_avg_content_generation_time_seconds": "# HELP autoblog_avg_content_generation_time_seconds 평균 콘텐츠 생성 시간 (초)\n# TYPE autoblog_avg_content_generation_time_seconds gauge",
            "autoblog_avg_publishing_time_seconds": "# HELP autoblog_avg_publishing_time_seconds 평균 게시 시간 (초)\n# TYPE autoblog_avg_publishing_time_seconds gauge",
            "autoblog_last_metrics_update_timestamp": "# HELP autoblog_last_metrics_update_timestamp 마지막 메트릭 업데이트 시간 (유닉스 타임스탬프)\n# TYPE autoblog_last_metrics_update_timestamp gauge",
            "autoblog_total_llm_cost_usd": "# HELP autoblog_total_llm_cost_usd 총 LLM 사용 비용 (USD)\n# TYPE autoblog_total_llm_cost_usd gauge"
        }
        
        # LLM 서비스별 메트릭 유형 및 설명 추가
        for service in SUPPORTED_LLM_SERVICES:
            metric_types[f"autoblog_{service}_tokens_used"] = f"# HELP autoblog_{service}_tokens_used {service.upper()} API 토큰 사용량\n# TYPE autoblog_{service}_tokens_used counter"
            metric_types[f"autoblog_{service}_cost_usd"] = f"# HELP autoblog_{service}_cost_usd {service.upper()} API 사용 비용 (USD)\n# TYPE autoblog_{service}_cost_usd gauge"
            metric_types[f"autoblog_{service}_requests"] = f"# HELP autoblog_{service}_requests {service.upper()} API 요청 횟수\n# TYPE autoblog_{service}_requests counter"
        
        # 각 메트릭을 Prometheus 형식으로 변환
        for metric, value in self.metrics.items():
            if metric in metric_types:
                prometheus_lines.append(metric_types[metric])
                prometheus_lines.append(f"{metric} {value}")
        
        return "\n".join(prometheus_lines)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP 요청 처리기"""
    
    def __init__(self, *args, **kwargs):
        self.metrics_collector = AutoBlogMetrics()
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """GET 요청 처리"""
        if self.path == '/metrics':
            # 메트릭 수집 및 응답 전송
            self.metrics_collector.collect_metrics()
            metrics_data = self.metrics_collector.format_prometheus()
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(metrics_data.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def log_message(self, format, *args):
        """로깅 메시지 핸들러"""
        logger.info(f"{self.address_string()} - {format % args}")


def run_server(port=9877):
    """메트릭 익스포터 서버 실행"""
    try:
        # 로그 디렉토리 생성
        os.makedirs("logs", exist_ok=True)
        
        # 서버 시작
        server_address = ('', port)
        httpd = HTTPServer(server_address, MetricsHandler)
        logger.info(f"AutoBlog 메트릭 익스포터가 포트 {port}에서 시작되었습니다.")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"서버 실행 중 오류: {e}")


if __name__ == "__main__":
    run_server() 