import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

import { clearDeepSeekConfig, getDeepSeekConfig, saveDeepSeekConfig } from "./api";

const sourceLabels: Record<string, string> = {
  environment: "进程环境变量（APP_DEEPSEEK_API_KEY）",
  database: "本页保存的密钥",
};

export function SettingsPage(): ReactNode {
  const queryClient = useQueryClient();
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const statusQuery = useQuery({
    queryKey: ["workstation", "settings", "deepseek"],
    queryFn: ({ signal }) => getDeepSeekConfig(signal),
  });

  function refreshStatus(): void {
    void queryClient.invalidateQueries({ queryKey: ["workstation", "settings", "deepseek"] });
  }

  const saveMutation = useMutation({
    mutationFn: () => saveDeepSeekConfig(apiKeyInput.trim()),
    onSuccess: () => {
      setApiKeyInput("");
      setNotice({ kind: "success", text: "已保存。正在重试的翻译任务会在下一次重试时直接使用该密钥，无需重启。" });
      refreshStatus();
    },
    onError: (error: Error) => setNotice({ kind: "error", text: error.message }),
  });

  const clearMutation = useMutation({
    mutationFn: () => clearDeepSeekConfig(),
    onSuccess: () => {
      setNotice({ kind: "success", text: "已清除本页保存的密钥。" });
      refreshStatus();
    },
    onError: (error: Error) => setNotice({ kind: "error", text: error.message }),
  });

  const status = statusQuery.data;

  return (
    <section className="ny-workstation-page" aria-labelledby="workstation-page-title">
      <p className="ny-workstation__eyebrow">设置</p>
      <h1 className="ny-workstation-page__title" id="workstation-page-title">运行时配置</h1>
      <p className="ny-workstation-page__copy">在此管理流水线需要的外部服务凭据，保存后立即生效。</p>

      <div
        style={{
          maxWidth: 560,
          marginTop: 24,
          padding: 16,
          border: "1px solid var(--ny-border)",
          background: "var(--ny-surface)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <KeyRound aria-hidden="true" size="var(--ny-icon-default)" strokeWidth="var(--ny-icon-stroke)" />
          <h2 style={{ margin: 0, fontSize: "1rem" }}>DeepSeek 校对密钥</h2>
        </div>
        <p className="ny-workstation-page__copy" style={{ marginTop: 8 }}>
          翻译阶段末尾的 DeepSeek 校对需要此密钥。优先使用 worker 进程环境变量，其次使用本页保存的密钥。
        </p>

        <p style={{ margin: "12px 0" }}>
          当前状态：
          {statusQuery.isLoading
            ? "读取中…"
            : status?.configured
              ? `已配置（来源：${sourceLabels[status.source ?? ""] ?? status.source}）`
              : "未配置"}
        </p>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (apiKeyInput.trim().length > 0) saveMutation.mutate();
          }}
        >
          <label className="ny-field" htmlFor="deepseek-api-key">API Key</label>
          <input
            className="ny-input"
            id="deepseek-api-key"
            onChange={(event) => setApiKeyInput(event.target.value)}
            placeholder="sk-…"
            type="password"
            value={apiKeyInput}
            autoComplete="off"
          />
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button
              className="ny-button ny-button--primary"
              disabled={saveMutation.isPending || apiKeyInput.trim().length === 0}
              type="submit"
            >
              保存密钥
            </button>
            <button
              className="ny-button ny-button--danger"
              disabled={clearMutation.isPending || !status?.configured || status.source !== "database"}
              onClick={() => clearMutation.mutate()}
              type="button"
            >
              清除
            </button>
          </div>
        </form>

        {notice !== null ? (
          <p
            role="status"
            style={{ marginTop: 12, color: notice.kind === "error" ? "var(--ny-danger, #b3261e)" : "inherit" }}
          >
            {notice.text}
          </p>
        ) : null}
      </div>
    </section>
  );
}
