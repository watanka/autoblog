#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GNews 파서에 대한 유닛 테스트
"""

import unittest
from unittest.mock import patch, Mock, MagicMock
import json
import os
import sys
from datetime import datetime, timedelta

# 테스트 대상 모듈 임포트를 위한 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.trends.parsers.gnews_parser import GNewsParser


class TestGNewsParser(unittest.TestCase):
    """GNewsParser 클래스에 대한 테스트"""

    def setUp(self):
        """각 테스트 전에 실행되는 설정"""
        self.test_config = {
            'trends': {
                'gnews': {
                    'api_key': '508256b08f03d46f2a09dc270eaef6a3',
                    'language': 'ko',
                    'country': 'kr',
                    'max_results': 5,
                    'categories': ['general', 'technology']
                },
                'max_trends': 5,
                'time_window_hours': 24,
                'min_article_count': 2,
                'analysis': {
                    'blacklist': ['성인', '음란', '도박']
                }
            }
        }
        self.parser = GNewsParser(self.test_config)

    def test_init(self):
        """초기화 테스트"""
        self.assertEqual(self.parser.api_key, '508256b08f03d46f2a09dc270eaef6a3')
        self.assertEqual(self.parser.language, 'ko')
        self.assertEqual(self.parser.country, 'kr')
        self.assertEqual(self.parser.max_results, 5)
        self.assertEqual(self.parser.categories, ['general', 'technology'])
        self.assertEqual(self.parser.max_trends, 5)
        self.assertEqual(self.parser.blacklist, ['성인', '음란', '도박'])

    @patch('src.trends.parsers.gnews_parser.requests.Session')
    def test_fetch_top_news(self, mock_session):
        """_fetch_top_news 메서드 테스트"""
        # Mock 응답 설정
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'articles': [
                {
                    'title': '테스트 기사 제목 1',
                    'description': '테스트 기사 설명 1',
                    'content': '테스트 기사 내용 1',
                    'url': 'https://example.com/article1',
                    'publishedAt': '2023-01-01T12:00:00Z',
                    'source': {
                        'name': '테스트 소스 1',
                        'url': 'https://example.com'
                    }
                },
                {
                    'title': '테스트 기사 제목 2',
                    'description': '테스트 기사 설명 2',
                    'content': '테스트 기사 내용 2',
                    'url': 'https://example.com/article2',
                    'publishedAt': '2023-01-01T13:00:00Z',
                    'source': {
                        'name': '테스트 소스 2',
                        'url': 'https://example2.com'
                    }
                }
            ]
        }
        
        # Mock 세션 설정
        mock_session.return_value.get.return_value = mock_response
        
        # 메서드 호출
        articles = self.parser._fetch_top_news('general')
        
        # 검증
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]['title'], '테스트 기사 제목 1')
        self.assertEqual(articles[0]['source']['name'], '테스트 소스 1')
        self.assertEqual(articles[0]['category'], 'general')
        
        # API 호출 검증
        mock_session.return_value.get.assert_called_once()
        args, kwargs = mock_session.return_value.get.call_args
        self.assertIn('https://gnews.io/api/v4/top-headlines', args)

    @patch('src.trends.parsers.gnews_parser.requests.Session')
    def test_search_news(self, mock_session):
        """_search_news 메서드 테스트"""
        # Mock 응답 설정
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'articles': [
                {
                    'title': '인공지능 관련 기사 1',
                    'description': '인공지능 기술에 대한 설명',
                    'content': '인공지능 기술 내용...',
                    'url': 'https://example.com/ai1',
                    'publishedAt': '2023-01-01T12:00:00Z',
                    'source': {
                        'name': 'AI 뉴스',
                        'url': 'https://ainews.com'
                    }
                }
            ]
        }
        
        # Mock 세션 설정
        mock_session.return_value.get.return_value = mock_response
        
        # 메서드 호출
        articles = self.parser._search_news('인공지능')
        
        # 검증
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['title'], '인공지능 관련 기사 1')
        self.assertEqual(articles[0]['keyword'], '인공지능')
        
        # API 호출 검증
        mock_session.return_value.get.assert_called_once()
        args, kwargs = mock_session.return_value.get.call_args
        self.assertIn('https://gnews.io/api/v4/search', args)

    def test_extract_keywords(self):
        """_extract_keywords 메서드 테스트"""
        # 한국어 키워드 추출 테스트
        text = "인공지능 기술이 발전하면서 새로운 일자리가 창출되고 있습니다."
        keywords = self.parser._extract_keywords(text)
        
        expected_keywords = [
            '인공지능', '기술', '발전', '새로운', '일자리', '창출',
            '인공지능 기술', '기술 발전', '발전 새로운', '새로운 일자리', '일자리 창출',
            '인공지능 기술 발전', '기술 발전 새로운', '발전 새로운 일자리', '새로운 일자리 창출'
        ]
        
        for keyword in expected_keywords:
            self.assertIn(keyword, keywords)
        
        # 특수문자 제거 테스트
        text_with_special = "인공지능(AI) 기술이 발전하면서 '새로운' 일자리가 창출되고 있습니다."
        keywords_clean = self.parser._extract_keywords(text_with_special)
        
        self.assertIn('인공지능', keywords_clean)
        self.assertIn('기술', keywords_clean)

    def test_is_valid_keyword(self):
        """_is_valid_keyword 메서드 테스트"""
        # 유효한 키워드
        self.assertTrue(self.parser._is_valid_keyword('인공지능'))
        self.assertTrue(self.parser._is_valid_keyword('빅데이터 분석'))
        
        # 블랙리스트에 있는 키워드
        self.assertFalse(self.parser._is_valid_keyword('성인 콘텐츠'))
        
        # 너무 짧은 키워드
        self.assertFalse(self.parser._is_valid_keyword('가'))
        
        # 숫자로만 이루어진 키워드
        self.assertFalse(self.parser._is_valid_keyword('12345'))

    @patch('src.trends.parsers.gnews_parser.GNewsParser._fetch_top_news')
    @patch('src.trends.parsers.gnews_parser.GNewsParser._search_news')
    def test_process_articles(self, mock_search, mock_fetch):
        """뉴스 기사 처리 메서드 테스트"""
        # 테스트 기사 데이터
        articles = [
            {
                'title': '인공지능 기술 혁신이 일어나고 있다',
                'description': '인공지능이 다양한 산업에 혁신을 가져오고 있습니다.',
                'url': 'https://example.com/article1',
                'source': {'name': '테크 뉴스'},
                'category': 'technology'
            },
            {
                'title': '인공지능 기술의 발전과 미래',
                'description': '인공지능 기술이 어떻게 발전하고 있는지 알아봅니다.',
                'url': 'https://example.com/article2',
                'source': {'name': '미래 뉴스'},
                'category': 'technology'
            },
            {
                'title': '클라우드 컴퓨팅 시장 성장세',
                'description': '클라우드 컴퓨팅 시장이 계속해서 성장하고 있습니다.',
                'url': 'https://example.com/article3',
                'source': {'name': '비즈니스 뉴스'},
                'category': 'business'
            }
        ]
        
        # 추가 검색 기사 데이터 (모킹)
        mock_search.return_value = [
            {
                'title': '인공지능 관련 추가 기사',
                'description': '인공지능에 대한 추가 정보',
                'url': 'https://example.com/article4',
                'source': {'name': '과학 뉴스'},
            }
        ]
        
        # 기사 처리 메서드 호출 (이름이 변경되었다고 가정)
        processed_articles = self.parser._process_articles(articles)
        
        # 검증
        self.assertGreaterEqual(len(processed_articles), 3)  # 최소 원본 기사 수만큼 있어야 함
        
        # 기사 내용 검증
        article = processed_articles[0]
        self.assertIn('title', article)
        self.assertIn('description', article)
        self.assertIn('url', article)
        self.assertIn('source', article)

    @patch('src.trends.parsers.gnews_parser.GNewsParser._fetch_top_news')
    def test_get_trends(self, mock_fetch):
        """get_trends 메서드 테스트 - 뉴스 기사 반환 기능"""
        # 각 카테고리별 가짜 기사 반환
        def mock_fetch_by_category(category):
            return [
                {
                    'title': f'{category} 관련 인공지능 기사',
                    'description': f'{category}에서 인공지능의 활용',
                    'url': f'https://example.com/{category}/1',
                    'source': {'name': '테스트 뉴스'},
                    'category': category
                },
                {
                    'title': f'{category} 분야의 블록체인 기술',
                    'description': f'{category}에서 블록체인 기술의 적용',
                    'url': f'https://example.com/{category}/2',
                    'source': {'name': '테스트 뉴스 2'},
                    'category': category
                }
            ]
        
        # 모킹 설정
        mock_fetch.side_effect = mock_fetch_by_category
        
        # 메서드 호출
        articles = self.parser.get_trends()
        
        # 검증
        expected_count = len(self.parser.categories) * 2  # 각 카테고리당 2개 기사
        self.assertEqual(len(articles), min(expected_count, self.parser.max_trends))  # max_trends 제한 고려
        
        # 기사 형식 검증
        for article in articles:
            self.assertIn('title', article)
            self.assertIn('description', article)
            self.assertIn('url', article)
            self.assertIn('source', article)
            self.assertIn('category', article)
            
        # 호출 횟수 검증 (카테고리 수만큼 호출되어야 함)
        self.assertEqual(mock_fetch.call_count, len(self.parser.categories))
        
        # API 키가 없는 경우 테스트
        self.parser.api_key = None
        articles_empty = self.parser.get_trends()
        self.assertEqual(articles_empty, [])

    @patch('src.trends.parsers.gnews_parser.GNewsParser._contains_korean')
    def test_extract_trending_articles(self, mock_contains_korean):
        """_extract_trending_articles 메서드 테스트"""
        # 모킹 설정
        mock_contains_korean.return_value = True
        
        # 테스트 기사 데이터
        articles = [
            {
                'title': '인공지능 기술 혁신',
                'description': '인공지능이 다양한 산업에 혁신을 가져오고 있습니다.',
                'url': 'https://example.com/article1',
                'published_at': '2023-01-01T12:00:00Z',
                'source': {'name': '테크 뉴스'},
                'category': 'technology'
            },
            {
                'title': '블록체인 시장 동향',
                'description': '블록체인 기술이 금융을 넘어 다양한 분야로 확장 중입니다.',
                'url': 'https://example.com/article2',
                'published_at': '2023-01-01T11:00:00Z',
                'source': {'name': '경제 뉴스'},
                'category': 'business'
            },
            {
                'title': '연예인 스캔들',
                'description': '최근 연예계 스캔들에 대한 기사입니다.',
                'url': 'https://example.com/article3',
                'published_at': '2023-01-01T13:00:00Z',
                'source': {'name': '연예 뉴스'},
                'category': 'entertainment'
            }
        ]
        
        # 메서드 호출
        trending_articles = self.parser._extract_trending_articles(articles)
        
        # 검증
        self.assertEqual(len(trending_articles), 3)
        
        # 트렌드 점수 필드 추가 여부 확인
        for article in trending_articles:
            self.assertIn('trend_score', article)
        
        # 정렬 검증 (트렌드 점수 기준 내림차순)
        for i in range(len(trending_articles) - 1):
            self.assertGreaterEqual(
                trending_articles[i].get('trend_score', 0),
                trending_articles[i+1].get('trend_score', 0)
            )


if __name__ == '__main__':
    unittest.main()
