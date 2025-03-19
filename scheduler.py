#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
자동화 블로그 시스템 스케줄러
config/default.yml 파일에 정의된 스케줄에 따라 블로그 자동화 작업을 실행합니다.
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime
import signal
import re

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from dotenv import load_dotenv

# 코어 모듈 임포트
from src.utils.config import ConfigLoader
from src.utils.logger import setup_logger

# 환경 변수 로드
load_dotenv()

def setup_logging(log_level='INFO'):
    """로깅 설정"""
    # 로그 디렉토리가 없으면 생성
    os.makedirs('logs', exist_ok=True)
    
    # 로거 설정
    log_file = f'logs/scheduler_{datetime.now().strftime("%Y%m%d")}.log'
    logger = setup_logger(
        log_level=log_level,
        log_dir='logs'
    )
    return logger

def parse_cron_schedule(schedule_str, logger):
    """
    cron 형식의 스케줄 문자열을 파싱합니다.
    
    Args:
        schedule_str (str): cron 형식의 스케줄 문자열 (예: '0 8 * * *')
        
    Returns:
        dict: 파싱된 스케줄 딕셔너리
    """
    if not schedule_str or not isinstance(schedule_str, str):
        return {'minute': '0', 'hour': '8', 'day': '*', 'month': '*', 'day_of_week': '*'}
    
    parts = schedule_str.strip().split()
    if len(parts) != 5:
        logger.warning(f"잘못된 cron 표현식: {schedule_str}, 기본값 사용")
        return {'minute': '0', 'hour': '8', 'day': '*', 'month': '*', 'day_of_week': '*'}
    
    return {
        'minute': parts[0],
        'hour': parts[1],
        'day': parts[2],
        'month': parts[3],
        'day_of_week': parts[4]
    }

def run_blog_automation(config, mode='full', logger=None):
    """
    블로그 자동화 작업을 실행합니다.
    
    Args:
        config (dict): 설정 객체
        mode (str): 실행 모드 ('full', 'trends', 'content', 'publish')
        logger (logging.Logger): 로거 객체
    """
    if logger:
        logger.info(f"블로그 자동화 작업 실행 시작: 모드={mode}")
    
    try:
        # main.py 스크립트 실행
        cmd = [sys.executable, 'main.py', f'--mode={mode}']
        
        # 로깅 설정
        if logger:
            log_level = logger.getEffectiveLevel()
            log_level_name = logging.getLevelName(log_level)
            cmd.append(f'--log-level={log_level_name}')
        
        # 현재 디렉토리에서 스크립트 실행
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 결과 대기
        stdout, stderr = process.communicate()
        
        # 결과 로깅
        if logger:
            if process.returncode == 0:
                logger.info(f"블로그 자동화 작업 성공적으로 완료됨: 모드={mode}")
                if stdout:
                    # 작업 ID 추출
                    job_id_match = re.search(r'작업 ID: (\d{8}_\d{6}_\w{8})', stdout)
                    if job_id_match:
                        job_id = job_id_match.group(1)
                        logger.info(f"생성된 작업 ID: {job_id}")
                    
                    logger.debug(f"작업 출력: {stdout}")
            else:
                logger.error(f"블로그 자동화 작업 실패: 모드={mode}, 종료 코드={process.returncode}")
                if stderr:
                    logger.error(f"오류 출력: {stderr}")
                if stdout:
                    logger.debug(f"작업 출력: {stdout}")
        
        return process.returncode == 0
        
    except Exception as e:
        if logger:
            logger.exception(f"블로그 자동화 작업 실행 중 예외 발생: {str(e)}")
        return False

def job_listener(event, logger):
    """
    스케줄러 작업 실행 이벤트 리스너
    
    Args:
        event: 스케줄러 이벤트
        logger: 로거 객체
    """
    if event.exception:
        logger.error(f'작업 실행 중 오류 발생: {event.exception}')
    else:
        logger.info(f'작업 {event.job_id} 성공적으로 실행됨')

def stop_scheduler(scheduler, logger, signal_num=None, frame=None):
    """
    스케줄러를 중지합니다.
    
    Args:
        scheduler: 스케줄러 객체
        logger: 로거 객체
        signal_num: 시그널 번호 (시그널 핸들러에서 사용)
        frame: 프레임 객체 (시그널 핸들러에서 사용)
    """
    logger.info("스케줄러 중지 요청 받음...")
    scheduler.shutdown()
    logger.info("스케줄러가 중지되었습니다.")

def main():
    """
    스케줄러 메인 함수
    """
    # 로깅 설정
    logger = setup_logging()
    logger.info(f"블로그 자동화 스케줄러 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 설정 로드
        config = ConfigLoader.load('config/default.yml')
        logger.info("설정 로드 완료")
        
        # 스케줄 설정 확인
        schedule_str = config.get('publishing', {}).get('docusaurus', {}).get('schedule', '0 8 * * *')
        logger.info(f"스케줄 설정: {schedule_str}")
        
        # 스케줄 파싱
        schedule = parse_cron_schedule(schedule_str, logger)
        logger.info(f"파싱된 스케줄: {schedule}")
        
        # 스케줄러 초기화
        scheduler = BackgroundScheduler()
        
        # 블로그 자동화 작업 스케줄링
        scheduler.add_job(
            run_blog_automation,
            CronTrigger(**schedule),
            args=[config, 'full', logger],
            id='blog_automation',
            name='블로그 자동화 작업'
        )
        
        # 이벤트 리스너 추가
        scheduler.add_listener(
            lambda event: job_listener(event, logger),
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        
        # 스케줄러 시작
        scheduler.start()
        logger.info("스케줄러 시작됨")
        
        # 즉시 한 번 실행하기 위한 선택 옵션
        run_now = input("블로그 자동화 작업을 지금 바로 실행하시겠습니까? (y/n): ").strip().lower()
        if run_now == 'y':
            logger.info("블로그 자동화 작업 즉시 실행...")
            run_blog_automation(config, 'full', logger)
        
        # 시그널 핸들러 설정 (Ctrl+C로 중지 가능)
        signal.signal(signal.SIGINT, lambda sig, frame: stop_scheduler(scheduler, logger, sig, frame))
        signal.signal(signal.SIGTERM, lambda sig, frame: stop_scheduler(scheduler, logger, sig, frame))
        
        # 스케줄러 상태 정보 출력
        next_run = scheduler.get_job('blog_automation').next_run_time
        logger.info(f"다음 스케줄 실행 시간: {next_run}")
        print(f"블로그 자동화 스케줄러가 실행 중입니다. 다음 실행 시간: {next_run}")
        print("스케줄러를 종료하려면 Ctrl+C를 누르세요.")
        
        # 메인 스레드 실행 상태 유지
        try:
            while True:
                time.sleep(60)  # 1분마다 상태 확인
                job = scheduler.get_job('blog_automation')
                if job:
                    next_run = job.next_run_time
                    print(f"\r다음 실행 시간: {next_run}", end="")
                else:
                    logger.warning("작업이 더 이상 스케줄러에 존재하지 않습니다.")
                    break
        except KeyboardInterrupt:
            logger.info("키보드 인터럽트 감지됨")
            stop_scheduler(scheduler, logger)
        
        logger.info("스케줄러 종료됨")
        return 0
        
    except Exception as e:
        logger.exception(f"스케줄러 실행 중 오류 발생: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 