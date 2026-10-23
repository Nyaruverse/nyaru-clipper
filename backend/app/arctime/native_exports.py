from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlmodel import Session, select

from app.arctime.subtitle_exports import ExportActivity, ExportOutput, ExportSnapshot
from app.arctime.subtitle_inputs import ExportRequest
from app.models_unified import OperationStep, UnifiedOperation, UnifiedPublication
from app.services.task_publication import Publisher
from app.services.task_requests import restore_request
from app.services.unified_files import checked_path

if TYPE_CHECKING:
    from app.arctime.unified_host import NativeHost


def export_snapshot(host: NativeHost, task_id: str) -> ExportSnapshot:
    with Session(host.engine) as session:
        operations = session.exec(select(UnifiedOperation).where(UnifiedOperation.task_id == task_id,
            UnifiedOperation.kind == 'export').order_by(UnifiedOperation.created_at)).all()
        rows = session.exec(select(UnifiedPublication).join(UnifiedOperation)
            .where(UnifiedOperation.task_id == task_id, UnifiedPublication.state == 'committed')).all()
        requests = {operation.id: json.loads(operation.snapshot_json).get('input', {}) for operation in operations}
        latest_state = operations[-1].state if operations else None
        metadata = {row.id: session.get(OperationStep, row.step_id).metadata_json for row in rows}
    outputs = []
    unavailable = False
    for row in rows:
        try:
            receipt = Publisher(host.engine, host.root).registered(row.id)
            product = next((member for member in receipt.outputs if member.role == 'product'), None)
            if product is None:
                continue
            step = json.loads(metadata[row.id])
            if 'request' in step:
                request = ExportRequest.model_validate(step['request'])
            else:
                body = restore_request(host.root, requests[row.operation_id])
                request = ExportRequest.model_validate(body['request'])
            extension = {'ass': 'ass', 'burn': 'mp4', 'arctime': 'zip'}[request.kind]
            outputs.append(ExportOutput(id=row.id[:20], kind=request.kind, video=request.video,
                bilingual=request.bilingual, filename=f'styled-{row.id[:20]}.{extension}', sha256=product.sha256, style=request.style))
        except (ValueError, OSError, KeyError):
            unavailable = True
    active = None
    if latest_state in {'queued', 'paused', 'running'}:
        active = ExportActivity(state='exporting', message='导出已排队' if latest_state != 'running' else '正在导出字幕')
    elif latest_state in {'failed', 'interrupted', 'cancelled'}:
        active = ExportActivity(state='interrupted' if latest_state == 'interrupted' else 'failed', message='导出未完成；已登记结果保留')
    elif latest_state == 'succeeded':
        active = ExportActivity(state='completed', message='字幕导出完成')
    if unavailable and latest_state not in {'queued', 'paused', 'running'}:
        active = ExportActivity(state='failed', message='部分已登记导出无法读取；原文件与记录已保留')
    return ExportSnapshot(outputs=outputs, active=active)


def export_file(host: NativeHost, task_id: str, name: str) -> Path:
    match = re.fullmatch(r'styled-([0-9a-f]{20})\.(ass|mp4|zip)', name)
    if match is None:
        raise HTTPException(404, '导出文件不存在')
    with Session(host.engine) as session:
        rows = session.exec(select(UnifiedPublication).join(UnifiedOperation).where(
            UnifiedOperation.task_id == task_id, UnifiedPublication.id.startswith(match.group(1)),
            UnifiedPublication.state == 'committed')).all()
    if len(rows) != 1:
        raise HTTPException(409, '导出身份不存在或不唯一，请检查记录')
    try:
        receipt = Publisher(host.engine, host.root).registered(rows[0].id)
        product = next(member for member in receipt.outputs if member.role == 'product')
        if Path(product.target).suffix != '.' + match.group(2):
            raise HTTPException(404, '导出格式与记录不一致')
        return checked_path(host.root, product.target)
    except (ValueError, OSError, StopIteration):
        raise HTTPException(409, '导出文件缺失或摘要不符；原文件与记录已保留') from None
