#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
로깅 설정 모듈
"""

import os
import logging
from datetime import datetime
from typing import Optional


def setup_logger(log_level: str = 'INFO', log_dir: Optional[str] = None) -> logging.Logger:
    """
    애플리케이션 로거를 설정합니다.
    
    Args:
        log_level (str): 로깅 레벨 ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        log_dir (Optional[str]): 로그 파일 저장 디렉토리
        
    Returns:
        logging.Logger: 설정된 로거 객체
    """
    # 로깅 레벨 매핑
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR
    }
    level = level_map.get(log_level.upper(), logging.INFO)
    
    # 로거 설정
    logger = logging.getLogger('autoblog')
    logger.setLevel(level)
    
    # 핸들러가 이미 설정되어 있으면 초기화하지 않음
    if logger.handlers:
        return logger
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # 포맷터
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (선택 사항)
    if log_dir:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(
            log_dir, 
            f"autoblog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger