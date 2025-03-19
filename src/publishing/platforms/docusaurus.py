#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Docusaurus 블로그 게시 구현
"""

import os
import logging
import base64
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from github import Github
from github import GithubException
import re

from src.core.interfaces import Publisher
from src.utils.metadata_enhancer import update_job_status, track_performance

class DocusaurusPublisher(Publisher):
    """GitHub 기반 Docusaurus 블로그 퍼블리셔 구현"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        DocusaurusPublisher를 초기화합니다.
        
        Args:
            config (Dict[str, Any]): 퍼블리셔 설정
                - github_token: GitHub API 액세스 토큰
                - repo_owner: GitHub 레포지토리 소유자
                - repo_name: GitHub 레포지토리 이름
                - branch: 대상 브랜치 (기본값: 'main')
                - blog_path: 블로그 포스트 경로 (기본값: 'blog')
                - commit_message: 커밋 메시지 템플릿
        """
        self.logger = logging.getLogger('autoblog.publishing.docusaurus')
        
        # GitHub 설정
        self.github_token = config.get('github', {}).get('token')
        if not self.github_token:
            self.github_token = os.environ.get('GITHUB_TOKEN')
            if not self.github_token:
                self.logger.error("GitHub 토큰이 설정되지 않았습니다.")
        
        # 레포지토리 설정
        self.repo_owner = config.get('publishing', {}).get('docusaurus', {}).get('repo_owner')
        self.repo_name = config.get('publishing', {}).get('docusaurus', {}).get('repo_name')
        self.branch = config.get('publishing', {}).get('docusaurus', {}).get('branch', 'main')
        self.blog_path = config.get('publishing', {}).get('docusaurus', {}).get('blog_path', 'blog')
        self.commit_msg_template = config.get('publishing', {}).get('docusaurus', {}).get('commit_message', '자동 포스팅: {title}')
        
        # 기본 저자 설정
        self.default_author = config.get('publishing', {}).get('docusaurus', {}).get('author', 'autoblog')
        
        # GitHub 클라이언트
        self._github = None
        self._repo = None
        
        if self.github_token:
            self.logger.info(f"DocusaurusPublisher 초기화 완료: {self.repo_owner}/{self.repo_name}")
    
    def _init_github(self):
        """
        GitHub 클라이언트를 초기화합니다.
        """
        if self._github is None and self.github_token:
            try:
                self._github = Github(self.github_token)
                self._repo = self._github.get_repo(f"{self.repo_owner}/{self.repo_name}")
                self.logger.info(f"GitHub 클라이언트 초기화 완료: {self.repo_owner}/{self.repo_name}")
                return True
            except Exception as e:
                self.logger.error(f"GitHub 클라이언트 초기화 실패: {str(e)}")
                self._github = None
                self._repo = None
                return False
        return False
        
    def _create_file(self, path: str, content: str, commit_message: str) -> Dict[str, Any]:
        """
        새 파일을 생성합니다.
        
        Args:
            path (str): 파일 경로
            content (str): 파일 내용
            commit_message (str): 커밋 메시지
            
        Returns:
            Dict[str, Any]: 결과 정보
        """
        # GitHub 클라이언트 초기화
        if not self._init_github():
            # GitHub 연결 실패 시 로컬에 저장
            return self._save_local(path, content)
            
        try:
            self.logger.info(f"GitHub에 새 파일 생성: {path}")
            
            # 폴더 경로 추출 (index.md를 제외한 경로)
            folder_path = os.path.dirname(path)
            post_slug = os.path.basename(folder_path)
            
            # GitHub에서는 폴더를 직접 생성할 수 없으므로, 파일을 생성하면서 필요한 폴더가 자동으로 생성됨
            result = self._repo.create_file(
                path=path,
                message=commit_message,
                content=content.encode('utf-8'),
                branch=self.branch
            )
            
            # 결과 URL 생성
            html_url = result.get('commit', {}).html_url
            
            # Docusaurus 블로그 URL 생성 (경로에서 blog/ 부분을 제거하고 slug 추출)
            slug = post_slug
            if '-' in post_slug:
                # YYYY-MM-DD-slug 형식에서 날짜 부분 제거
                slug = '-'.join(post_slug.split('-')[3:])
            
            blog_url = f"https://{self.repo_owner}.github.io/{self.repo_name.replace('.github.io', '')}/blog/{slug}"
            
            return {
                'status': 'success',
                'url': blog_url,
                'github_url': html_url,
                'path': path
            }
            
        except Exception as e:
            self.logger.error(f"GitHub 파일 생성 실패: {str(e)}")
            # 오류 발생 시 로컬에 저장
            return self._save_local(path, content)
    
    def _update_file(self, path: str, content: str, commit_message: str) -> Dict[str, Any]:
        """
        기존 파일을 업데이트합니다.
        
        Args:
            path (str): 파일 경로
            content (str): 파일 내용
            commit_message (str): 커밋 메시지
            
        Returns:
            Dict[str, Any]: 결과 정보
        """
        # GitHub 클라이언트 초기화
        if not self._init_github():
            # GitHub 연결 실패 시 로컬에 저장
            return self._save_local(path, content)
            
        try:
            self.logger.info(f"GitHub 파일 업데이트: {path}")
            file_contents = self._repo.get_contents(path, ref=self.branch)
            result = self._repo.update_file(
                path=path,
                message=commit_message,
                content=content.encode('utf-8'),
                sha=file_contents.sha,
                branch=self.branch
            )
            
            # 결과 URL 생성
            html_url = result.get('commit', {}).html_url
            
            # 폴더 경로 추출 (index.md를 제외한 경로)
            folder_path = os.path.dirname(path)
            post_slug = os.path.basename(folder_path)
            
            # Docusaurus 블로그 URL 생성 (경로에서 blog/ 부분을 제거하고 slug 추출)
            slug = post_slug
            if '-' in post_slug:
                # YYYY-MM-DD-slug 형식에서 날짜 부분 제거
                slug = '-'.join(post_slug.split('-')[3:])
            
            blog_url = f"https://{self.repo_owner}.github.io/{self.repo_name.replace('.github.io', '')}/blog/{slug}"
            
            return {
                'status': 'success',
                'url': blog_url,
                'github_url': html_url,
                'path': path
            }
            
        except Exception as e:
            self.logger.error(f"GitHub 파일 업데이트 실패: {str(e)}")
            # 오류 발생 시 로컬에 저장
            return self._save_local(path, content)
    
    def _save_local(self, path: str, content: str) -> Dict[str, Any]:
        """
        콘텐츠를 로컬 파일 시스템에 저장합니다.
        
        Args:
            path (str): 파일 경로
            content (str): 파일 내용
            
        Returns:
            Dict[str, Any]: 결과 정보
        """
        try:
            local_path = path
            if not os.path.isabs(local_path):
                # 상대 경로인 경우 로컬 디렉토리에 저장
                local_dir = os.path.join('output', os.path.dirname(local_path))
                os.makedirs(local_dir, exist_ok=True)
                local_path = os.path.join('output', local_path)
            
            self.logger.info(f"콘텐츠를 로컬에 저장: {local_path}")
            
            # 디렉토리가 없으면 생성
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 파일 저장
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 폴더 경로 추출 (index.md를 제외한 경로)
            folder_path = os.path.dirname(local_path)
            post_slug = os.path.basename(folder_path)
            
            # slug 추출
            slug = post_slug
            if '-' in post_slug:
                # YYYY-MM-DD-slug 형식에서 날짜 부분 제거
                slug = '-'.join(post_slug.split('-')[3:])
                
            return {
                'status': 'success',
                'message': '콘텐츠가 로컬에 저장되었습니다.',
                'path': local_path,
                'url': f"file://{os.path.abspath(folder_path)}",
                'slug': slug
            }
            
        except Exception as e:
            self.logger.error(f"로컬 저장 실패: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _generate_slug(self, title: str) -> str:
        """
        제목에서 slug를 생성합니다.
        
        Args:
            title (str): 포스트 제목
            
        Returns:
            str: 생성된 slug
        """
        # 한글 포함 여부 확인
        has_korean = any(ord(char) >= 0xAC00 and ord(char) <= 0xD7A3 for char in title)
        
        if has_korean:
            # 타임스탬프 기반 슬러그
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            return f"post-{timestamp}"
        else:
            # 영문/숫자 기반 슬러그
            slug = title.lower()
            slug = ''.join(c if c.isalnum() else '-' for c in slug)
            slug = '-'.join(filter(None, slug.split('-')))
            return slug

    def publish(self, contents: List[Dict[str, Any]], job_id: str = None) -> Dict[str, Any]:
        """
        콘텐츠를 Docusaurus 블로그에 게시합니다.
        
        Args:
            contents (List[Dict[str, Any]]): 게시할 콘텐츠 목록
            job_id (str, optional): 작업 ID
            
        Returns:
            Dict[str, Any]: 게시 결과 정보
        """
        if not contents:
            self.logger.warning("게시할 콘텐츠가 없습니다.")
            return {
                'status': 'error',
                'message': '게시할 콘텐츠가 없습니다.',
                'total': 0,
                'success': 0,
                'failed': 0,
                'posts': []
            }
        
        # 성능 측정 시작
        if job_id:
            start_time = time.time()
            update_job_status(job_id, "in_progress")
        
        result = {
            'status': 'success',
            'message': '',
            'total': len(contents),
            'success': 0,
            'failed': 0,
            'posts': []
        }
        
        try:
            # contents가 리스트가 아닌 경우 리스트로 변환
            if not isinstance(contents, list):
                self.logger.warning(f"콘텐츠가 리스트가 아닙니다. 타입: {type(contents)}")
                if isinstance(contents, dict) or isinstance(contents, str):
                    contents = [contents]
                else:
                    raise TypeError(f"지원되지 않는 콘텐츠 타입: {type(contents)}")
            
            # 각 콘텐츠 게시
            for content in contents:
                try:
                    post_result = self._publish_single_content(content)
                    if post_result.get('status') == 'success':
                        result['success'] += 1
                    else:
                        result['failed'] += 1
                    result['posts'].append(post_result)
                except Exception as e:
                    self.logger.error(f"콘텐츠 게시 중 오류 발생: {str(e)}")
                    result['failed'] += 1
                    result['posts'].append({
                        'status': 'error',
                        'message': str(e),
                        'title': content.get('title', '제목 없음') if isinstance(content, dict) else '제목 없음',
                        'url': None
                    })
            
            # 결과 메시지 설정
            if result['failed'] == 0:
                result['message'] = f"모든 콘텐츠가 성공적으로 게시되었습니다. (총 {result['total']}개)"
            else:
                result['message'] = f"{result['success']}개 게시 성공, {result['failed']}개 게시 실패."
            
            # 성능 측정 완료
            if job_id:
                end_time = time.time()
                track_performance(job_id, "publishing", start_time, end_time)
                update_job_status(job_id, "success")
            
            return result
            
        except Exception as e:
            self.logger.error(f"게시 과정에서 오류 발생: {str(e)}")
            
            # 오류 발생 시에도 메타데이터 기록
            if job_id:
                end_time = time.time()
                track_performance(job_id, "publishing", start_time, end_time)
                update_job_status(job_id, "failed", str(e))
            
            # 실패 결과 반환
            result['status'] = 'error'
            result['message'] = f"게시 과정에서 오류가 발생했습니다: {str(e)}"
            return result

    def _publish_single_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        단일 콘텐츠를 Docusaurus 블로그에 게시합니다.
        
        Args:
            content (Dict[str, Any]): 게시할 콘텐츠
            
        Returns:
            Dict[str, Any]: 게시 결과 정보
        """
        try:
            # 문자열인 경우 처리
            if isinstance(content, str):
                self.logger.warning("문자열 콘텐츠를 처리합니다. 제목 없이 내용만 게시합니다.")
                # 타임스탬프 기반 제목 생성
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                title = f"자동 생성 포스트 {timestamp}"
                content_dict = {
                    'title': title,
                    'content': content,
                    'authors': [self.default_author],
                    'tags': [],
                    'description': '자동 생성 포스트'
                }
                content = content_dict
            
            # 필수 필드 확인
            if 'title' not in content or 'content' not in content:
                self.logger.error("콘텐츠에 필수 필드(title 또는 content)가 없습니다.")
                return {
                    'status': 'error',
                    'message': '콘텐츠에 필수 필드가 없습니다.',
                    'title': content.get('title', '제목 없음'),
                    'url': None
                }
            
            # 콘텐츠 내용 가져오기
            content_text = content.get('content', '')
            
            # 콘텐츠가 이미 프론트매터를 포함하고 있는지 확인
            has_frontmatter = content_text.startswith('---')
            markdown_content = content_text
            
            # 프론트매터가 없는 경우에만 새로 추가
            if not has_frontmatter:
                # 파일명 생성 (slugify)
                title_slug = self._slugify(content.get('title', ''))
                date_str = datetime.now().strftime('%Y-%m-%d')
                
                # 메타데이터 구성
                metadata = {
                    'title': content.get('title', '제목 없음'),
                    'authors': content.get('authors', [self.default_author]),
                    'tags': content.get('tags', []),
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'description': content.get('description', ''),
                    'slug': title_slug  # 명시적으로 slug 지정
                }
                
                # 소스 정보가 있으면 메타데이터에 추가
                if 'source_article' in content:
                    source = content['source_article']
                    if isinstance(source, dict) and source.get('url') and source.get('title'):
                        metadata['original_source'] = {
                            'url': source.get('url', ''),
                            'title': source.get('title', ''),
                            'site': source.get('source', {}).get('name', '') if isinstance(source.get('source'), dict) else ''
                        }
                
                # Frontmatter 생성
                frontmatter = self._create_frontmatter(metadata)
                
                # 마크다운 파일 내용 생성
                markdown_content = frontmatter + '\n\n' + content_text
                self.logger.info("새 프론트매터가 추가되었습니다.")
            else:
                self.logger.info("콘텐츠에 이미 프론트매터가 포함되어 있습니다. 그대로 사용합니다.")
                
                # 제목과 슬러그 추출 (프론트매터에서)
                title_match = re.search(r'title: "(.*?)"', content_text)
                if title_match:
                    title = title_match.group(1)
                else:
                    title = content.get('title', '제목 없음')
                
                slug_match = re.search(r'slug: (.*?)$', content_text, re.MULTILINE)
                if slug_match:
                    title_slug = slug_match.group(1).strip()
                else:
                    title_slug = self._slugify(title)
            
            # 폴더 생성 (Docusaurus 권장 구조: YYYY-MM-DD-slug/index.md)
            date_str = datetime.now().strftime('%Y-%m-%d')
            folder_name = f"{date_str}-{title_slug}"
            folder_path = os.path.join(self.blog_path, folder_name)
            filepath = os.path.join(folder_path, "index.md")
            
            # GitHub에 파일 생성
            commit_message = self.commit_msg_template.format(title=content.get('title', '자동 생성 포스트'))
            create_result = self._create_file(filepath, markdown_content, commit_message)
            
            if create_result.get('status') == 'success':
                self.logger.info(f"'{content.get('title')}' 콘텐츠가 GitHub에 게시되었습니다.")
                
                return {
                    'status': 'success',
                    'message': '콘텐츠가 성공적으로 게시되었습니다.',
                    'title': content.get('title', '제목 없음'),
                    'filepath': filepath,
                    'folder': folder_path,
                    'url': create_result.get('url', ''),
                    'github_url': create_result.get('github_url', '')
                }
            else:
                self.logger.error(f"GitHub 게시 실패: {create_result.get('error', '알 수 없는 오류')}")
                return {
                    'status': 'error',
                    'message': f"GitHub 게시 실패: {create_result.get('error', '알 수 없는 오류')}",
                    'title': content.get('title', '제목 없음'),
                    'filepath': filepath,
                    'url': None
                }
            
        except Exception as e:
            self.logger.error(f"콘텐츠 게시 중 오류 발생: {str(e)}")
            return {
                'status': 'error',
                'message': f"콘텐츠 게시 중 오류 발생: {str(e)}",
                'title': content.get('title', '제목 없음') if isinstance(content, dict) else '제목 없음',
                'url': None
            }

    def _slugify(self, text: str) -> str:
        """
        텍스트를 URL 친화적인 슬러그로 변환합니다.
        
        Args:
            text (str): 변환할 텍스트
            
        Returns:
            str: 슬러그화된 텍스트
        """
        # 소문자로 변환하고 공백을 하이픈으로 교체
        slug = text.lower().strip()
        
        # 영어가 아닌 문자는 transliteration (로마자화)
        slug = slug.replace(' ', '-')
        
        # 알파벳, 숫자, 하이픈만 유지
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        
        # 연속된 하이픈 제거
        slug = re.sub(r'-+', '-', slug)
        
        return slug

    def _create_frontmatter(self, metadata: Dict[str, Any]) -> str:
        """
        Docusaurus 마크다운 파일의 프론트매터를 생성합니다.
        
        Args:
            metadata (Dict[str, Any]): 메타데이터
            
        Returns:
            str: YAML 형식의 프론트매터
        """
        frontmatter = ['---']
        
        # 기본 메타데이터 필드
        for key, value in metadata.items():
            if key == 'authors' or key == 'tags':
                if not value:
                    continue
                frontmatter.append(f"{key}:")
                for item in value:
                    frontmatter.append(f"  - {item}")
            elif key == 'original_source':
                if isinstance(value, dict) and value.get('url') and value.get('title'):
                    frontmatter.append(f"{key}:")
                    frontmatter.append(f"  url: {value.get('url')}")
                    frontmatter.append(f"  title: {value.get('title')}")
                    if value.get('site'):
                        frontmatter.append(f"  site: {value.get('site')}")
            else:
                frontmatter.append(f"{key}: {value}")
        
        frontmatter.append('---')
        
        return '\n'.join(frontmatter)

    def _write_to_file(self, filepath: str, content: str) -> None:
        """
        콘텐츠를 파일에 저장합니다.
        
        Args:
            filepath (str): 파일 경로
            content (str): 저장할 콘텐츠
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
