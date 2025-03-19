#!/usr/bin/env python
"""
AutoBlog 모니터링 시스템 실행 스크립트

사용법:
python run_monitoring.py [--port PORT]
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# src 디렉터리를 파이썬 모듈 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

# 모니터링 모듈 임포트
from src.monitoring.metrics_exporter import run_server

def main():
    """메인 함수"""
    # 명령줄 인수 파싱
    parser = argparse.ArgumentParser(description='AutoBlog 모니터링 시스템')
    parser.add_argument('--port', type=int, default=9877, help='익스포터 리스닝 포트 (기본값: 9877)')
    
    args = parser.parse_args()
    
    # 로그 디렉터리 생성
    os.makedirs('logs', exist_ok=True)
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"logs/monitoring_{datetime.now().strftime('%Y%m%d')}.log")
        ]
    )
    
    logger = logging.getLogger('autoblog_monitoring')
    logger.info(f"AutoBlog 모니터링 시스템 시작 (포트: {args.port})")
    
    try:
        # 메트릭 익스포터 서버 실행
        run_server(port=args.port)
    except KeyboardInterrupt:
        logger.info("사용자 입력으로 모니터링 시스템 종료")
    except Exception as e:
        logger.error(f"모니터링 시스템 실행 중 오류 발생: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main()) 