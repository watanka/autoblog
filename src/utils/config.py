#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
설정 및 시크릿 로더 모듈
"""

import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class ConfigLoader:
    """설정 파일 및 시크릿 로딩 클래스"""
    
    @staticmethod
    def load(config_path: str) -> Dict[str, Any]:
        """
        설정 파일과 시크릿 파일을 로드합니다.
        
        Args:
            config_path (str): 기본 설정 파일 경로
            
        Returns:
            Dict[str, Any]: 설정과 시크릿이 병합된 설정 객체
            
        Raises:
            FileNotFoundError: 설정 파일을 찾을 수 없을 때 발생
            yaml.YAMLError: YAML 파싱 오류 발생 시
        """
        # 설정 파일 경로 검증
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
        
        # 기본 설정 로드
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"YAML 파싱 오류 (설정 파일): {str(e)}")
        
        # 시크릿 로드 (파일이 존재하는 경우)
        secrets = {}
        # 환경 변수에서 시크릿 로드 (최우선)
        # OpenAI API 키
        openai_api_key = os.environ.get('OPENAI_API_KEY')
        if openai_api_key:
            if 'openai' not in config:
                config['openai'] = {}
            config['openai']['api_key'] = openai_api_key
        
        # GitHub 토큰
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            if 'github' not in config:
                config['github'] = {}
            config['github']['token'] = github_token
        
        # GNews API 키
        gnews_api_key = os.environ.get('GNEWS_API_KEY')
        if gnews_api_key:
            if 'gnews' not in config:
                config['gnews'] = {}
            config['gnews']['api_key'] = gnews_api_key
        
        return config