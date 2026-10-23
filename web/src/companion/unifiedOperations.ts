import createClient from 'openapi-fetch';
import { useQuery } from '@tanstack/react-query';
import type { components, paths } from '../generated/api-schema';
import { workstationKeys } from '../workstation/api/queryKeys';

export type Operation = components['schemas']['OperationView'];
export type OperationsSnapshot = components['schemas']['OperationsSnapshot'];
export const client = createClient<paths>({baseUrl: window.location.origin, fetch: (...args) => globalThis.fetch(...args)});

export function result<T>(value: {data?: T; error?: unknown; response: Response}, conflict = '队列状态已变化，请重新读取后重试'): T {
  if (!value.response.ok || value.data === undefined) {
    const detail = value.error && typeof value.error === 'object' && 'detail' in value.error ? value.error.detail : null;
    throw new Error(value.response.status === 409 ? conflict : typeof detail === 'string' ? detail : '本地操作失败，请检查服务状态');
  }
  return value.data;
}

export function useUnifiedOperations(enabled: boolean) {
  return useQuery({queryKey: workstationKeys.operations, enabled, queryFn: async ({signal}) =>
    result(await client.GET('/api/v2/operations', {signal})), refetchInterval: 15000});
}

export async function admissions(snapshot: OperationsSnapshot) {
  return result(await client.POST('/api/v2/operations/queue', {body: {expected_revision: snapshot.revision, paused: !snapshot.paused}}));
}

export async function reorder(snapshot: OperationsSnapshot, orderedIds: string[]) {
  return result(await client.POST('/api/v2/operations/reorder', {body: {expected_revision: snapshot.revision, ordered_ids: orderedIds}}));
}

export async function waiting(operation: Operation, state: 'queued' | 'paused', priority?: number) {
  return result(await client.POST('/api/v2/operations/{operation_id}/waiting', {
    params: {path: {operation_id: operation.id}}, body: {state, priority}}));
}

export async function cancel(operation: Operation) {
  return result(await client.POST('/api/v2/operations/{operation_id}/cancel', {params: {path: {operation_id: operation.id}}}));
}

export async function retry(operation: Operation, acknowledge: boolean) {
  return result(await client.POST('/api/v2/operations/{operation_id}/retry', {
    params: {path: {operation_id: operation.id}}, body: {acknowledge_external_outcome: acknowledge}}));
}
