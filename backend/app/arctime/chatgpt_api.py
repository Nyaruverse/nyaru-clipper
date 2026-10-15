from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.arctime import companion_llm, translation
from app.arctime.companion_manager import JobManager


class LLMConfig(BaseModel):
    provider: Literal['deepseek', 'chatgpt']
    model: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9._-]+$')


def chatgpt_router(manager: JobManager) -> APIRouter:
    router = APIRouter()

    @router.get('/companion-api/chatgpt')
    def status():
        return manager.chatgpt.status()

    @router.post('/companion-api/chatgpt/login')
    def login(request: Request):
        with manager.lock:
            if manager.active:
                raise HTTPException(409, '请等当前任务完成后再连接 ChatGPT')
            try:
                return {'url': manager.chatgpt.begin(str(request.base_url).rstrip('/') + '/auth/callback')}
            except (ValueError, OSError):
                raise HTTPException(409, '无法开始 ChatGPT 登录；请检查本地授权配置后重试') from None

    @router.get('/auth/callback')
    def callback(request: Request):
        headers = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                   'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"}
        success = False
        with manager.lock:
            if not manager.active:
                query = request.query_params
                try:
                    if any(len(query.getlist(name)) > 1 for name in ('code', 'state', 'client_id', 'error')):
                        raise ValueError('重复回调参数')
                    manager.chatgpt.complete(code=query.get('code', ''), state=query.get('state', ''),
                                            client_id=query.get('client_id'), error=query.get('error'))
                    success = True
                except (ValueError, OSError):
                    success = False
        if success:
            return RedirectResponse('/auth/result', status_code=303, headers=headers)
        message = '登录未完成或已过期，请返回 Nyaru Clipper 重新连接。'
        return HTMLResponse('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Nyaru Clipper</title><p>'
                            + message + '</p></html>', status_code=200 if success else 400, headers=headers)

    @router.get('/auth/result')
    def result():
        return HTMLResponse('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Nyaru Clipper</title>'
                            '<p>授权结果已处理，请返回 Nyaru Clipper 查看连接状态并选择模型。</p></html>',
                            headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                                     'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"})

    @router.post('/companion-api/chatgpt/logout')
    def logout():
        with manager.lock:
            if manager.active:
                raise HTTPException(409, '请等当前任务完成后再退出 ChatGPT')
            try:
                manager.chatgpt.logout()
            except (ValueError, OSError):
                raise HTTPException(409, 'ChatGPT 退出未完成，请检查网络后重试') from None
        return manager.chatgpt.status()

    @router.get('/companion-api/chatgpt/models')
    def models():
        try:
            return manager.chatgpt.models()
        except (ValueError, OSError):
            raise HTTPException(409, '无法读取订阅模型；请检查 ChatGPT 连接与授权后重试') from None

    @router.post('/companion-api/llm-config')
    def configure(payload: LLMConfig):
        if payload.provider == 'deepseek' and payload.model not in translation.MODELS:
            raise HTTPException(422, 'DeepSeek 仅支持 Flash')
        if payload.provider == 'chatgpt':
            try:
                choices = manager.chatgpt.models()
            except (ValueError, OSError):
                raise HTTPException(409, '请先登录 ChatGPT 并授权订阅额度') from None
            if payload.model not in {item['slug'] for item in choices}:
                raise HTTPException(422, '请选择当前 ChatGPT 账号可用的模型')
        with manager.lock:
            previous = (manager.llm_provider, manager.chatgpt_model, manager.translation_model)
            manager.llm_provider = payload.provider
            if payload.provider == 'chatgpt':
                manager.chatgpt_model = payload.model
            else:
                manager.translation_model = payload.model
            try:
                companion_llm.persist(manager)
            except (OSError, ValueError):
                manager.llm_provider, manager.chatgpt_model, manager.translation_model = previous
                raise HTTPException(409, '模型配置保存失败；请检查数据目录权限') from None
            manager.config_error = None
        return {'llm_provider': manager.llm_provider, 'llm_model': payload.model,
                'llm_configured': companion_llm.configured(manager)}

    return router
