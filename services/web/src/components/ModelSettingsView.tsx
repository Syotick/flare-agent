import { useEffect, useState, type ReactNode } from "react";
import {
  Bot, CheckCircle2, Cloud, Cpu, KeyRound, Loader2, PlugZap, Save, Sparkles, Trash2, XCircle,
} from "lucide-react";
import {
  getModelPresets, getModelSettings, saveModelSettings, testModelConnection,
  type ModelConfigBody, type ModelPreset, type ModelSettings, type ModelTestResult,
} from "../api";
import { cn } from "../lib/utils";

const SOURCE_LABEL: Record<string, string> = {
  env: "环境变量",
  file: "本地文件",
  none: "未配置",
};

const SOURCE_CLS: Record<string, string> = {
  env: "bg-info/15 text-info border border-info/30",
  file: "bg-muted text-muted-foreground border border-border",
  none: "bg-muted text-muted-foreground border border-border",
};

const PROVIDER_META: Record<string, { label: string; icon: typeof Cpu; badge: string }> = {
  mock: { label: "内置模拟", icon: Bot, badge: "bg-muted text-muted-foreground" },
  anthropic: { label: "Anthropic 协议", icon: Sparkles, badge: "bg-primary/10 text-primary" },
  openai: { label: "OpenAI 兼容", icon: Cpu, badge: "bg-success/10 text-success" },
};

function providerMeta(provider: string) {
  return PROVIDER_META[provider] ?? { label: "自定义协议", icon: Cloud, badge: "bg-muted text-muted-foreground" };
}

function field(label: string, children: ReactNode, hint?: string) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[12px] font-medium text-muted-foreground">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-muted-foreground/70">{hint}</span>}
    </label>
  );
}

const inputCls =
  "rounded-lg border border-border bg-card px-3 py-2 text-[13px] text-foreground outline-none transition-colors focus:border-primary disabled:opacity-50";

export default function ModelSettingsView() {
  const [cfg, setCfg] = useState<ModelSettings | null>(null);
  const [presets, setPresets] = useState<ModelPreset[]>([]);
  const [provider, setProvider] = useState("mock");
  const [baseUrl, setBaseUrl] = useState("");
  const [modelName, setModelName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [test, setTest] = useState<ModelTestResult | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    getModelSettings()
      .then((s) => {
        setCfg(s);
        setProvider(s.provider);
        setBaseUrl(s.base_url);
        setModelName(s.model_name);
      })
      .catch((err: Error) => setError(err.message));
    getModelPresets().then(setPresets).catch(() => undefined);
  };

  useEffect(() => {
    load();
  }, []);

  // 根据当前生效配置回填选中的供应商卡片（能匹配预设就高亮，否则视为自定义）
  useEffect(() => {
    if (!cfg || !presets.length) return;
    if (cfg.provider === "mock") {
      setSelectedPresetId("mock");
    } else {
      const hit = presets.find((p) => p.provider === cfg.provider && p.base_url === cfg.base_url);
      setSelectedPresetId(hit ? hit.id : null);
    }
  }, [cfg, presets]);

  const applyPreset = (p: ModelPreset | null) => {
    setSelectedPresetId(p ? p.id : "mock");
    if (!p) {
      setProvider("mock");
      setBaseUrl("");
      setModelName("");
      return;
    }
    setProvider(p.provider);
    if (p.base_url) setBaseUrl(p.base_url);
    if (p.models.length) setModelName(p.models[0]);
  };

  const applyCustomProvider = (v: string) => {
    setProvider(v);
    setSelectedPresetId(null);
  };

  const bodyFromForm = (): ModelConfigBody => {
    const body: ModelConfigBody = {
      provider,
      base_url: baseUrl.trim(),
      model_name: modelName.trim(),
    };
    if (apiKey !== "") body.api_key = apiKey; // 留空 = 保持已存 key（不发）
    return body;
  };

  const doSave = async () => {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const next = await saveModelSettings(bodyFromForm());
      setCfg(next);
      setApiKey("");
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const doTest = async () => {
    setBusy(true);
    setError("");
    setTest(null);
    try {
      setTest(await testModelConnection(bodyFromForm()));
    } catch (err) {
      setTest({ ok: false, mode: provider, error: (err as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const doClearKey = async () => {
    setBusy(true);
    setError("");
    try {
      const next = await saveModelSettings({ api_key: "" }); // 空串 = 清除已存 key
      setCfg(next);
      setApiKey("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const src = SOURCE_LABEL[cfg?.api_key_source ?? "none"] ?? "未配置";
  const srcCls = SOURCE_CLS[cfg?.api_key_source ?? "none"] ?? SOURCE_CLS.none;
  // 当前选中预设的模型候选（chips 点击即选）
  const candidateModels =
    presets.find((p) => p.id === selectedPresetId)?.models ?? [];

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="mx-auto flex w-full max-w-[760px] flex-col gap-4 px-6 py-6 pb-8">
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-primary" />
          <h1 className="text-lg font-semibold">模型设置</h1>
        </div>
        <p className="text-[12px] text-muted-foreground">
          选择供应商并填入 API Key，即可接入真实大模型。Key 只在服务端保存，本页不显示明文。
        </p>

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
            {error}
          </div>
        )}

        {/* 当前生效状态 */}
        <div className="rounded-xl border border-border bg-card/70 p-4">
          <div className="text-[12px] font-medium text-muted-foreground">当前使用</div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px]">
            <span className="font-mono text-foreground">{cfg?.provider ?? "-"}</span>
            <span className="max-w-[60%] truncate font-mono text-muted-foreground">
              {cfg?.base_url ?? ""}
            </span>
            <span className="font-mono text-muted-foreground">{cfg?.model_name ?? ""}</span>
            <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[10px]", srcCls)}>
              Key：{src}
            </span>
          </div>
        </div>

        {/* 供应商选择（CC Switch 风格卡片） */}
        <div>
          <div className="mb-2 text-[12px] font-medium text-muted-foreground">选择供应商</div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            <button
              type="button"
              onClick={() => applyPreset(null)}
              className={cn(
                "flex flex-col items-start gap-1 rounded-xl border p-3 text-left transition-colors",
                selectedPresetId === "mock"
                  ? "border-primary bg-primary/5"
                  : "border-border bg-card/70 hover:border-primary/50"
              )}
            >
              <span className="flex items-center gap-1.5 text-[13px] font-medium">
                <Bot className="h-4 w-4 text-primary" />
                内置模拟
              </span>
              <span className="text-[10px] text-muted-foreground">无需 Key，本地开发调试</span>
            </button>
            {presets.map((p) => {
              const meta = providerMeta(p.provider);
              const Icon = meta.icon;
              const active = selectedPresetId === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => applyPreset(p)}
                  className={cn(
                    "flex flex-col items-start gap-1 rounded-xl border p-3 text-left transition-colors",
                    active
                      ? "border-primary bg-primary/5"
                      : "border-border bg-card/70 hover:border-primary/50"
                  )}
                >
                  <span className="flex items-center gap-1.5 text-[13px] font-medium">
                    <Icon className="h-4 w-4 text-primary" />
                    {p.name}
                  </span>
                  <span className={cn("rounded-full px-1.5 py-0.5 text-[9px]", meta.badge)}>
                    {meta.label}
                  </span>
                  <span className="max-w-full truncate font-mono text-[10px] text-muted-foreground">
                    {p.base_url}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 配置表单 */}
        <div className="flex flex-col gap-3.5 rounded-xl border border-border bg-card/70 p-4">
          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            {field(
              "供应商协议",
              <select
                className={inputCls}
                value={provider}
                onChange={(e) => applyCustomProvider(e.target.value)}
              >
                <option value="mock">mock（内置模拟模型，无需 Key）</option>
                <option value="openai">openai（OpenAI 兼容）</option>
                <option value="anthropic">anthropic（Anthropic / Claude 原生）</option>
              </select>
            )}
            {field(
              "Base URL",
              <input
                className={inputCls}
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={
                  provider === "anthropic"
                    ? "https://api.anthropic.com"
                    : provider === "mock"
                      ? "（内置模拟无需填写）"
                      : "https://api.deepseek.com/v1"
                }
                disabled={provider === "mock"}
              />
            )}
          </div>

          {field("模型名称", <input className={inputCls} value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder={provider === "mock" ? "（内置模拟忽略）" : "claude-sonnet-4-5"} />, "可留空跟随预设；mock 模式忽略")}

          {candidateModels.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-muted-foreground">模型：</span>
              {candidateModels.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setModelName(m)}
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 font-mono text-[10px] transition-colors",
                    modelName === m
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                  )}
                >
                  {m}
                </button>
              ))}
            </div>
          )}

          {field(
            "API Key",
            <div className="relative">
              <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                className={cn(inputCls, "w-full pl-9")}
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  cfg?.has_api_key
                    ? "已配置 Key（留空保持不变，输入新值覆盖）"
                    : "输入 API Key（仅存服务端，不回显）"
                }
                autoComplete="off"
              />
            </div>,
            "Key 仅保存在服务端。生产环境建议改用环境变量注入。"
          )}

          <div className="flex flex-wrap items-center gap-2">
            <button
              className="flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-[12px] font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              onClick={doSave}
              disabled={busy}
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              保存并生效
            </button>
            <button
              className="flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-2 text-[12px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
              onClick={doTest}
              disabled={busy}
            >
              <PlugZap className="h-3.5 w-3.5" />
              测试连接
            </button>
            {cfg?.has_api_key && (
              <button
                className="flex items-center gap-1.5 rounded-lg border border-destructive/30 px-3.5 py-2 text-[12px] text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"
                onClick={doClearKey}
                disabled={busy}
              >
                <Trash2 className="h-3.5 w-3.5" />
                清除已存 Key
              </button>
            )}
            {saved && (
              <span className="flex items-center gap-1 text-[12px] text-success">
                <CheckCircle2 className="h-3.5 w-3.5" />
                已保存，对新建任务生效
              </span>
            )}
          </div>

          {test && (
            <div
              className={cn(
                "flex flex-col gap-2 rounded-lg border px-3 py-2.5 text-[12px]",
                test.ok
                  ? "border-success/30 bg-success/10 text-success"
                  : "border-destructive/30 bg-destructive/10 text-destructive"
              )}
            >
              <span className="flex items-center gap-1.5 font-medium">
                {test.ok ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : (
                  <XCircle className="h-3.5 w-3.5" />
                )}
                连通性测试（{test.mode}）
              </span>
              {test.ok ? (
                test.models && test.models.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {test.models.map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setModelName(m)}
                        className="rounded-full border border-success/30 bg-muted px-2 py-0.5 font-mono text-[10px] text-foreground transition-colors hover:border-success"
                        title="点击使用该模型"
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                ) : (
                  <span>连接成功，但未发现可用模型</span>
                )
              ) : (
                <span className="font-mono text-[11px]">{test.error}</span>
              )}
            </div>
          )}
        </div>

        {/* 说明 */}
        <div className="rounded-xl border border-dashed border-border p-4 text-[11px] leading-relaxed text-muted-foreground">
          <p className="font-medium text-foreground">配置说明</p>
          <p className="mt-1">保存的配置优先于默认值；生产环境请用环境变量注入 Key。保存后新任务立即生效。</p>
        </div>
      </div>
    </div>
  );
}
