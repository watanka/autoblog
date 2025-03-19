#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Docusaurus 퍼블리셔 테스트 스크립트
"""

import os
import json
import logging
import sys
import unittest
from unittest import mock
from datetime import datetime
from typing import Dict, Any

# 모듈 임포트를 위한 경로 추가 - 상위 디렉토리(프로젝트 루트)를 추가합니다.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 설정 로더 임포트
from src.utils.config import ConfigLoader

# Docusaurus 퍼블리셔 임포트
from src.publishing.platforms.docusaurus import DocusaurusPublisher
from github import GithubException

def setup_logging():
    """로깅 설정을 초기화합니다."""
    # 로그 디렉토리 생성
    os.makedirs('logs', exist_ok=True)
    
    # 로거 설정
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(f'logs/publisher_test_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger()

# 테스트 케이스 클래스 정의
class TestDocusaurusPublisher(unittest.TestCase):
    """Docusaurus 퍼블리셔 테스트 클래스"""
    
    def setUp(self):
        """테스트 환경 설정"""
        # 로깅 설정
        self.logger = setup_logging()
        
        # 테스트용 설정 생성
        self.test_config = {
            'publishing': {
                'docusaurus': {
                    'repo_owner': 'test-owner',
                    'repo_name': 'test-repo',
                    'branch': 'main',
                    'blog_path': 'blog',
                    'commit_message': '자동 포스팅: {title}'
                }
            },
            'github': {
                'token': 'fake-github-token'
            }
        }
        
        # 테스트용 콘텐츠 생성
        self.test_content = {
            'title': '테스트 블로그 포스트',
            'formatted_content': '---\nslug: test-post\ntitle: 테스트 블로그 포스트\nauthors: autoblog\ntag: [test]\n---\n\n테스트 블로그 포스트 내용입니다.',
            'slug': 'test-post'
        }
    
    @mock.patch('src.publishing.platforms.docusaurus.Github')
    def test_init(self, mock_github):
        """퍼블리셔 초기화 테스트"""
        publisher = DocusaurusPublisher(self.test_config)
        
        # 설정이 올바르게 로드되었는지 확인
        self.assertEqual(publisher.repo_owner, 'test-owner')
        self.assertEqual(publisher.repo_name, 'test-repo')
        self.assertEqual(publisher.branch, 'main')
        self.assertEqual(publisher.blog_path, 'blog')
        self.assertEqual(publisher.github_token, 'fake-github-token')
    
    @mock.patch('src.publishing.platforms.docusaurus.Github')
    def test_generate_slug(self, mock_github):
        """슬러그 생성 기능 테스트"""
        publisher = DocusaurusPublisher(self.test_config)
        
        # 영문 제목으로 슬러그 생성
        eng_title = "This is a Test Title"
        eng_slug = publisher._generate_slug(eng_title)
        self.assertTrue(eng_slug.endswith('this-is-a-test-title'))
        self.assertTrue('-' in eng_slug)
        
        # 한글 제목으로 슬러그 생성
        kor_title = "이것은 테스트 제목입니다"
        kor_slug = publisher._generate_slug(kor_title)
        self.assertTrue(kor_slug.startswith('post-'))
        self.assertTrue(len(kor_slug) > 5)
    
    @mock.patch('src.publishing.platforms.docusaurus.Github')
    def test_publish_no_token(self, mock_github):
        """토큰 없는 상태에서 게시 실패 테스트"""
        config_without_token = self.test_config.copy()
        config_without_token['github'] = {'token': None}
        
        publisher = DocusaurusPublisher(config_without_token)
        result = publisher.publish(self.test_content)
        
        # 토큰이 없으면 오류가 발생해야 함
        self.assertEqual(result['status'], 'error')
        self.assertTrue('GitHub 토큰이 없어' in result['error'])
    
    @mock.patch('src.publishing.platforms.docusaurus.Github')
    def test_publish_new_file(self, mock_github):
        """새 파일 게시 테스트"""
        # 모킹 설정
        mock_repo = mock.MagicMock()
        mock_repo.get_contents.side_effect = GithubException(404, {'message': 'Not Found'})
        mock_repo.create_file.return_value = {
            'commit': mock.MagicMock(html_url='https://github.com/test-owner/test-repo/commit/abcdef')
        }
        
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.return_value = mock_repo
        
        # 퍼블리셔 초기화 및 게시
        publisher = DocusaurusPublisher(self.test_config)
        result = publisher.publish(self.test_content)
        
        # 새 파일이 생성되었는지 확인
        mock_repo.create_file.assert_called_once()
        self.assertEqual(result['status'], 'success')
        self.assertTrue('test-owner.github.io' in result['url'])
        # 새로운 폴더 구조가 URL에 반영되었는지 확인
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertTrue(f"{today}-test-post" in result['path'])
        self.assertTrue('index.md' in result['path'])
    
    @mock.patch('src.publishing.platforms.docusaurus.Github')
    def test_publish_update_file(self, mock_github):
        """기존 파일 업데이트 테스트"""
        # 모킹 설정
        mock_file_content = mock.MagicMock(sha='file-sha-123')
        mock_repo = mock.MagicMock()
        mock_repo.get_contents.return_value = mock_file_content
        mock_repo.update_file.return_value = {
            'commit': mock.MagicMock(html_url='https://github.com/test-owner/test-repo/commit/abcdef')
        }
        
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.return_value = mock_repo
        
        # 퍼블리셔 초기화 및 게시
        publisher = DocusaurusPublisher(self.test_config)
        result = publisher.publish(self.test_content)
        
        # 파일이 업데이트되었는지 확인
        mock_repo.update_file.assert_called_once()
        self.assertEqual(result['status'], 'success')
        self.assertTrue('test-owner.github.io' in result['url'])
        # 새로운 폴더 구조가 URL에 반영되었는지 확인
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertTrue(f"{today}-test-post" in result['path'])
        self.assertTrue('index.md' in result['path'])
    
    @mock.patch('src.publishing.platforms.docusaurus.Github')
    def test_error_handling(self, mock_github):
        """오류 처리 테스트"""
        # 모킹 설정
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.side_effect = Exception("테스트 오류")
        
        # 퍼블리셔 초기화 및 게시
        publisher = DocusaurusPublisher(self.test_config)
        result = publisher.publish(self.test_content)
        
        # 오류가 올바르게 처리되었는지 확인
        self.assertEqual(result['status'], 'error')
        self.assertTrue('테스트 오류' in result['error'])

def manual_test():
    """
    수동 테스트를 위한 함수
    실제 GitHub API를 호출하므로 실행 시 주의
    """
    logger = setup_logging()
    logger.info("=== Docusaurus 퍼블리셔 수동 테스트 시작 ===")
    
    # 환경 변수에서 GitHub 토큰 가져오기
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        logger.error("GITHUB_TOKEN 환경 변수가 설정되지 않았습니다.")
        return
    
    # 설정 로드
    config = ConfigLoader().load('../config/default.yml')
    logger.info("설정 로드 완료")
    
    # GitHub 토큰 설정
    if not config.get('github'):
        config['github'] = {}
    config['github']['token'] = github_token
    
    try:
        # 퍼블리셔 초기화
        publisher = DocusaurusPublisher(config)
        logger.info("Docusaurus 퍼블리셔 초기화 완료")
        
        # authors.yml 파일이 없는 경우 생성
        # 이 파일은 Docusaurus에서 참조하는 작성자 정보가 포함됨
        try:
            authors_path = f"{config['publishing']['docusaurus']['blog_path']}/authors.yml"
            publisher._repo.get_contents(authors_path, ref=publisher.branch)
            logger.info(f"authors.yml 파일이 이미 존재합니다")
        except GithubException as e:
            if e.status == 404:  # 파일이 없음
                authors_content = """# blog/authors.yml 파일
# Docusaurus 블로그 저자 정보

autoblog:
  name: AutoBlog System
  title: 자동 블로깅 시스템
  url: https://github.com/watanka/autoblog
  image_url: https://github.com/watanka.png
"""
                result = publisher._create_file(
                    authors_path,
                    authors_content,
                    "Add authors.yml for blog posts"
                )
                if result['status'] == 'success':
                    logger.info(f"authors.yml 파일 생성 완료: {result['github_url']}")
                else:
                    logger.error(f"authors.yml 파일 생성 실패: {result.get('error')}")
            else:
                logger.error(f"authors.yml 파일 확인 중 오류: {str(e)}")
        
        # 테스트용 콘텐츠 준비
        test_slug = f"test-post-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        test_content = {
            'title': f'테스트 포스트 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            'formatted_content': f"""---
slug: {test_slug}
title: 테스트 포스트 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
authors: autoblog
tags: [test, automation]
---

# 테스트 포스트

이 포스트는 AutoBlog 시스템에서 자동으로 생성된 테스트 포스트입니다.
생성 시간: {datetime.now().isoformat()}

## Docusaurus 폴더 구조 테스트

이 포스트는 새로운 Docusaurus 폴더 구조(blog/YYYY-MM-DD-{title}/index.md)를 테스트하기 위해 작성되었습니다.
""",
            'slug': test_slug
        }
        
        # 게시 테스트
        logger.info(f"콘텐츠 게시 시도: {test_content['title']}")
        result = publisher.publish(test_content)
        
        if result['status'] == 'success':
            logger.info(f"게시 성공: {result['url']}")
            print(f"\n게시 성공: {result['url']}")
            print(f"파일 경로: {result['path']}")
        else:
            logger.error(f"게시 실패: {result.get('error', '알 수 없는 오류')}")
            print(f"\n게시 실패: {result.get('error', '알 수 없는 오류')}")
        
        logger.info("=== Docusaurus 퍼블리셔 수동 테스트 완료 ===")
        
    except Exception as e:
        logger.exception(f"오류 발생: {str(e)}")

if __name__ == "__main__":
    # 명령행 인수에 따라 자동 테스트 또는 수동 테스트 실행
    if len(sys.argv) > 1 and sys.argv[1] == '--manual':
        manual_test()
    else:
        unittest.main() 