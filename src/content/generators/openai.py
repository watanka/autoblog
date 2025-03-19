#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OpenAI API를 사용한 콘텐츠 생성기 구현
"""

import logging
import json
from typing import Dict, Any, List, Optional
import time

from openai import OpenAI
from openai.types.chat import ChatCompletion

from src.core.interfaces import ContentGenerator
from src.utils.metadata_enhancer import track_performance, track_llm_usage, update_job_status

class OpenAIContentGenerator(ContentGenerator):
    """OpenAI API를 사용하여 콘텐츠를 생성하는 구현체"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        OpenAI 콘텐츠 생성기를 초기화합니다.
        
        Args:
            config (Dict[str, Any]): OpenAI API 및 관련 설정
        """
        self.logger = logging.getLogger('autoblog.content.openai')
        
        # OpenAI 설정
        self.api_key = config.get('openai', {}).get('api_key')
        self.model = config.get('openai', {}).get('model', 'gpt-4o-mini')
        self.max_tokens = config.get('openai', {}).get('max_tokens', 2000)
        self.temperature = config.get('openai', {}).get('temperature', 0.7)
        
        # 프롬프트 템플릿
        self.blog_prompt_template = config.get('openai', {}).get('prompts', {}).get('blog_post', '')
        self.target_audience = config.get('openai', {}).get('target_audience', '일반')
        # OpenAI 클라이언트 초기화
        if not self.api_key:
            self.logger.error("OpenAI API 키가 설정되지 않았습니다.")
        else:
            self.client = OpenAI(api_key=self.api_key)
            self.logger.info(f"OpenAI 클라이언트 초기화 완료 (모델: {self.model})")
    
    def generate_content(self, article: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """
        주어진 뉴스 기사에 대한 블로그 콘텐츠를 생성합니다.
        
        Args:
            article (Dict[str, Any]): 콘텐츠를 생성할 뉴스 기사 정보
            job_id (str): 작업 ID
                
        Returns:
            Dict[str, Any]: 생성된 콘텐츠 (최소한 'title'과 'content' 키를 포함)
        """
        if not self.api_key:
            self.logger.error("OpenAI API 키가 없어 콘텐츠를 생성할 수 없습니다.")
            return {
                'title': '[API 키 오류] 콘텐츠를 생성할 수 없습니다',
                'content': '### OpenAI API 키가 설정되지 않았습니다.\n\n콘텐츠를 생성하려면 유효한 API 키를 설정해 주세요.'
            }
        
        # 성능 측정 시작
        start_time = time.time()
        
        try:
            # 프롬프트 생성
            prompt = self._create_prompt(article)
            self.logger.debug(f"생성된 프롬프트 길이: {len(prompt)} 글자")
            
            # OpenAI API 호출
            self.logger.info(f"OpenAI API 호출 시작: 기사 '{article.get('title', '')[:30]}...'")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 전문적인 블로그 작가입니다. 제공된 뉴스 기사를 바탕으로 흥미로운 블로그 게시물을 작성합니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            elapsed_time = time.time() - start_time
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            self.logger.info(f"OpenAI API 호출 완료: {elapsed_time:.2f}초 소요")
            self.logger.info(f"토큰 사용량: 입력={prompt_tokens}, 출력={completion_tokens}, 총={total_tokens}개")

            
            # 응답 처리
            response_content = response.choices[0].message.content
            
            try:
                # JSON 파싱
                result = json.loads(response_content)
                
                # 필수 필드 확인
                if 'title' not in result or 'content' not in result:
                    self.logger.warning(f"API 응답에 필수 필드가 없습니다: {result.keys()}")
                    result = self._ensure_required_fields(result, article)
                
                # 메타데이터 추가
                result['source_article'] = {
                    'title': article.get('title', ''),
                    'url': article.get('url', ''),
                    'source': article.get('source', {}).get('name', '')
                }
                result['generated_with'] = self.model
                
                # 토큰 사용량 및 비용 추적
                track_llm_usage(
                    job_id=job_id,
                    service_name="openai",
                    tokens_used=total_tokens,
                    requests_made=1,
                    model_name=self.model
                )
                
                # 성능 측정 완료
                end_time = time.time()
                track_performance(job_id, "content_generation", start_time, end_time)
                
                return result
                
            except json.JSONDecodeError:
                self.logger.error(f"JSON 파싱 오류: {response_content[:100]}...")
                result = self._create_fallback_content(article, response_content)
                
                # 성능 측정은 여전히 수행
                end_time = time.time()
                track_performance(job_id, "content_generation", start_time, end_time)
                
                return result
            
        except Exception as e:
            self.logger.error(f"콘텐츠 생성 중 오류 발생: {str(e)}")
            
            # 오류 발생 시에도 메타데이터 기록
            end_time = time.time()
            track_performance(job_id, "content_generation", start_time, end_time)
            update_job_status(job_id, "failed", str(e))
            
            return {
                'title': f"[오류] {article.get('title', '')}",
                'content': f"### 콘텐츠 생성 중 오류가 발생했습니다.\n\n오류: {str(e)}\n\n원본 기사: {article.get('url', '')}"
            }
    
    def estimate_cost(self, article: Dict[str, Any]) -> float:
        """
        주어진 뉴스 기사에 대한 콘텐츠 생성 비용을 예측합니다.
        
        Args:
            article (Dict[str, Any]): 콘텐츠를 생성할 뉴스 기사 정보
            
        Returns:
            float: 예상 비용 (달러)
        """
        # 프롬프트 생성
        prompt = self._create_prompt(article)
        
        # 토큰 수 추정 (영어 기준 대략 1 토큰 = 4 글자)
        estimated_prompt_tokens = len(prompt) / 4
        estimated_completion_tokens = self.max_tokens
        
        # 모델별 가격 (1K 토큰당 USD)
        model_prices = {
            'gpt-4': {'input': 0.03, 'output': 0.06},
            'gpt-4o': {'input': 0.01, 'output': 0.03},
            'gpt-4o-mini': {'input': 0.0015, 'output': 0.0060},
            'gpt-3.5-turbo': {'input': 0.0015, 'output': 0.002}
        }
        
        # 기본 가격 (GPT-3.5-turbo 기준)
        price_per_1k_input = 0.0015
        price_per_1k_output = 0.002
        
        # 선택한 모델에 맞는 가격 적용
        if self.model in model_prices:
            price_per_1k_input = model_prices[self.model]['input']
            price_per_1k_output = model_prices[self.model]['output']
        
        # 비용 계산
        input_cost = (estimated_prompt_tokens / 1000) * price_per_1k_input
        output_cost = (estimated_completion_tokens / 1000) * price_per_1k_output
        total_cost = input_cost + output_cost
        
        return total_cost
    
    def _create_prompt(self, article: Dict[str, Any]) -> str:
        """
        뉴스 기사 정보를 기반으로 프롬프트를 생성합니다.
        
        Args:
            article (Dict[str, Any]): 콘텐츠를 생성할 뉴스 기사 정보
            
        Returns:
            str: 생성된 프롬프트
        """
        # 기본 프롬프트 템플릿 사용
        prompt = self.blog_prompt_template
        
        # 변수 치환
        prompt = prompt.replace('[분야]', ', '.join(article.get('estimated_categories', ['일반'])))
        prompt = prompt.replace('[주제]', article.get('title', ''))
        
        # 독자층 설정
        prompt = prompt.replace('[독자층 설명]', self.target_audience)
        
        # 핵심 키워드 설정
        keywords = article.get('recommended_tags', [])
        if len(keywords) < 3:
            # 키워드가 부족한 경우 제목에서 추출
            title_words = article.get('title', '').split()
            keywords.extend([word for word in title_words if len(word) > 3 and word not in keywords][:5-len(keywords)])
        
        prompt = prompt.replace('[주요 키워드 3-5개]', ', '.join(keywords[:5]))
        
        # 기사 정보 추가
        prompt += f"\n\n원본 기사 정보:\n"
        prompt += f"제목: {article.get('title', '')}\n"
        prompt += f"설명: {article.get('description', '')}\n"
        
        # 전체 기사 내용이 있는 경우 추가
        if 'full_content' in article and article['full_content']:
            prompt += f"\n기사 전문:\n{article['full_content'][:4000]}...\n"
        elif 'content' in article:
            prompt += f"\n기사 내용 발췌:\n{article['content']}\n"
        
        # 태그 추가
        if article.get('recommended_tags'):
            prompt += f"\n추천 태그: {', '.join(article.get('recommended_tags', []))}\n"
        
        # 콘텐츠 포맷 지정
        prompt += "\n반환 형식은 반드시 다음과 같은 JSON 구조여야 합니다:\n"
        prompt += "{\n  \"title\": \"블로그 제목\",\n  \"content\": \"마크다운 형식의 블로그 내용\"\n}"
        
        return prompt
    
    def _ensure_required_fields(self, result: Dict[str, Any], article: Dict[str, Any]) -> Dict[str, Any]:
        """
        응답 결과에 필수 필드가 있는지 확인하고, 없으면 추가합니다.
        
        Args:
            result (Dict[str, Any]): API 응답 결과
            article (Dict[str, Any]): 원본 기사 정보
            
        Returns:
            Dict[str, Any]: 필수 필드가 추가된 결과
        """
        if 'title' not in result:
            result['title'] = article.get('title', '제목 없음')
            
        if 'content' not in result:
            # content 필드가 없으면 다른 필드의 내용을 content로 사용
            content_candidates = ['text', 'body', 'blog_content', 'article']
            for candidate in content_candidates:
                if candidate in result:
                    result['content'] = result[candidate]
                    break
            else:
                # 대체할 내용이 없으면 기본 메시지 생성
                result['content'] = f"## {article.get('title', '제목 없음')}\n\n{article.get('description', '')}"
        
        return result
    
    def _create_fallback_content(self, article: Dict[str, Any], api_response: str) -> Dict[str, Any]:
        """
        API 응답 처리 중 오류가 발생한 경우 대체 콘텐츠를 생성합니다.
        
        Args:
            article (Dict[str, Any]): 원본 기사 정보
            api_response (str): API 응답 원문
            
        Returns:
            Dict[str, Any]: 생성된 대체 콘텐츠
        """
        title = article.get('title', '제목 없음')
        description = article.get('description', '')
        
        content = f"## {title}\n\n"
        content += f"{description}\n\n"
        content += "---\n\n"
        
        # API 응답에서 마크다운 형식의 내용 추출 시도
        if "##" in api_response or "```" in api_response:
            content += api_response
        else:
            content += f"원본 기사: {article.get('url', '')}"
        
        return {
            'title': title,
            'content': content,
            'source_article': {
                'title': title,
                'url': article.get('url', ''),
                'source': article.get('source', {}).get('name', '')
            },
            'generated_with': self.model,
            'is_fallback': True
        }
