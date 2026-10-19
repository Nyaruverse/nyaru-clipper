import type { components } from "../../../generated/api-schema";

import { workstationClient } from "../../api/client";

export type DeepSeekConfigStatus = components["schemas"]["DeepSeekConfigStatus"];

export async function getDeepSeekConfig(signal?: AbortSignal): Promise<DeepSeekConfigStatus> {
  const { data, error } = await workstationClient.GET("/api/runtime/config/deepseek", { signal });
  if (error !== undefined || data === undefined) throw new Error("无法读取校对配置");
  return data;
}

export async function saveDeepSeekConfig(apiKey: string): Promise<DeepSeekConfigStatus> {
  const { data, error } = await workstationClient.PUT("/api/runtime/config/deepseek", {
    body: { api_key: apiKey },
  });
  if (error !== undefined || data === undefined) throw new Error("保存校对配置失败");
  return data;
}

export async function clearDeepSeekConfig(): Promise<DeepSeekConfigStatus> {
  const { data, error } = await workstationClient.DELETE("/api/runtime/config/deepseek");
  if (error !== undefined || data === undefined) throw new Error("清除校对配置失败");
  return data;
}
