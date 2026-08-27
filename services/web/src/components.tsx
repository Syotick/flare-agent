import { useEffect, useState } from "react";
import {
  ActionIcon,
  Badge,
  Button,
  Code,
  Group,
  NumberInput,
  Paper,
  ScrollArea,
  Text,
  Textarea,
  TextInput,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import type { Item, ToolResult } from "./types";
import type { TaskDetail } from "./api";
import {
  IconChevron,
  IconClose,
  IconPlus,
  IconSearch,
  IconSend,
  IconSpark,
  IconStop,
  IconTool,
  IconTrash,
} from "./icons";

// 打字机流式文本
export function StreamText({ text, done }: { text: string; done: boolean }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    setShown(0);
  }, [text]);
  useEffect(() => {
    if (done || shown >= text.length) return;
    const t = window.setTimeout(() => setShown((s) => Math.min(s + 2, text.length)), 12);
    return () => window.clearTimeout(t);
  }, [shown, done, text]);
  return (
    <span>
      {text.slice(0, shown)}
      {!done && <span className="cursor" />}
    </span>
  );
}

// 用户消息
export function UserBubble({ text }: { text: string }) {
  return (
    <div className="row user">
      <div className="bubble user-bubble">{text}</div>
    </div>
  );
}

// 助手消息（带流式 + 品牌头像）
export function AssistantBubble({ text, done }: { text: string; done: boolean }) {
  return (
    <div className="row assistant">
      <div className="avatar">
        <IconSpark size={14} />
      </div>
      <div className="bubble assistant-bubble">
        <StreamText text={text} done={done} />
      </div>
    </div>
  );
}

// 工具调用卡（Codex 风格）
export function ToolCard({
  name,
  args,
  status,
  result,
}: {
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done";
  result?: ToolResult;
}) {
  const [open, setOpen] = useState(false);
  const ok = result ? result.ok : true;
  const tag = status === "running" ? "running" : ok ? result?.error_code || "done" : result?.error_code || "error";
  return (
    <div className="row tool-row">
      <Paper className="toolblock" radius="md" withBorder>
        <UnstyledButton className="tool-btn" onClick={() => setOpen(!open)}>
          <span className="tool-icon">
            <IconTool size={14} />
          </span>
          <Code fz={12.5}>{name}</Code>
          <Badge
            ml="auto"
            size="sm"
            variant="light"
            color={!ok ? "red" : status === "running" ? "yellow" : "green"}
            className="tool-tag"
          >
            {tag}
          </Badge>
          <span className={"chev" + (open ? " open" : "")}>
            <IconChevron dir="down" size={13} />
          </span>
        </UnstyledButton>
        {open && (
          <div className="tool-detail">
            <div className="tool-kv">
              <span className="tool-kv-key">args</span>
              <pre>{JSON.stringify(args, null, 2)}</pre>
            </div>
            {result && (
              <div className="tool-kv">
                <span className="tool-kv-key">output</span>
                <pre className={ok ? "" : "err"}>{result.content}</pre>
              </div>
            )}
          </div>
        )}
      </Paper>
    </div>
  );
}

// 状态行
export function StatusLine({ text, tone }: { text: string; tone: "info" | "warn" | "error" }) {
  return <div className={"sys " + tone}>{text}</div>;
}

// 渲染入口
export function renderItem(it: Item) {
  switch (it.kind) {
    case "user":
      return <UserBubble key={it.id} text={it.text} />;
    case "assistant":
      return <AssistantBubble key={it.id} text={it.msg.text} done={it.msg.done} />;
    case "tool":
      return (
        <ToolCard
          key={it.id}
          name={it.name}
          args={it.args}
          status={it.status}
          result={it.result}
        />
      );
    case "status":
      return <StatusLine key={it.id} text={it.text} tone={it.tone} />;
  }
}

// ===== 会话侧边栏（WorkBuddy 式） =====

function relTime(ts: number): string {
  const ms = Date.now() - ts * 1000;
  if (ms < 60000) return "刚刚";
  if (ms < 3600000) return Math.floor(ms / 60000) + " 分钟前";
  if (ms < 86400000) return Math.floor(ms / 3600000) + " 小时前";
  const d = new Date(ts * 1000);
  return d.getMonth() + 1 + "/" + d.getDate();
}

function groupByDate(tasks: TaskDetail[]): { label: string; items: TaskDetail[] }[] {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 86400000;
  const buckets: [string, (t: TaskDetail) => boolean][] = [
    ["今天", (t) => t.created_at >= start],
    ["昨天", (t) => t.created_at >= start - day && t.created_at < start],
    ["近 7 天", (t) => t.created_at >= start - 7 * day && t.created_at < start - day],
    ["更早", (t) => t.created_at < start - 7 * day],
  ];
  const out: { label: string; items: TaskDetail[] }[] = [];
  for (const [label, pred] of buckets) {
    const items = tasks.filter(pred);
    if (items.length > 0) out.push({ label, items });
  }
  return out;
}

export function Sidebar(props: {
  tasks: TaskDetail[];
  activeTaskId: string | null;
  onPick: (taskId: string) => void;
  onNew: () => void;
  onDelete: (taskId: string) => void;
}) {
  const { tasks, activeTaskId, onPick, onNew, onDelete } = props;
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const filtered = q
    ? tasks.filter((t) => (t.task_input || "").toLowerCase().indexOf(q) >= 0)
    : tasks;
  const groups = groupByDate(filtered);
  return (
    <div className="sidebar-inner">
      <Button
        fullWidth
        variant="light"
        color="flare"
        leftSection={<IconPlus size={14} />}
        onClick={onNew}
        mb="sm"
      >
        新对话
      </Button>
      <TextInput
        leftSection={<IconSearch size={13} />}
        placeholder="搜索会话…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        rightSection={
          query ? (
            <ActionIcon size="sm" variant="subtle" color="gray" onClick={() => setQuery("")}>
              <IconClose size={12} />
            </ActionIcon>
          ) : undefined
        }
        mb="sm"
        size="sm"
      />
      <ScrollArea className="sidebar-scroll">
        {filtered.length === 0 && (
          <Text size="sm" c="dimmed" ta="center" py="lg">
            {tasks.length === 0 ? "还没有会话，发起一个任务吧" : "没有匹配的会话"}
          </Text>
        )}
        {groups.map((g) => (
          <div key={g.label}>
            <Text size="xs" fw={600} c="dimmed" tt="uppercase" pl="sm" pt="md" pb={4} fz={11}>
              {g.label}
            </Text>
            {g.items.map((t) => (
              <button
                key={t.task_id}
                className={"sidebar-item" + (t.task_id === activeTaskId ? " active" : "")}
                onClick={() => onPick(t.task_id)}
              >
                <Text size="sm" fw={activeTaskId === t.task_id ? 600 : 400} truncate>
                  {t.task_input}
                </Text>
                <Group gap={6} mt={4} align="center">
                  <span className={"si-dot " + t.status} />
                  <Text size="xs" c="dimmed" fz={11} tt="capitalize">
                    {t.status}
                  </Text>
                  <Text size="xs" c="dimmed" fz={10.5} ml="auto" style={{ fontFamily: "var(--mono)" }}>
                    {relTime(t.created_at)}
                  </Text>
                  <Tooltip label="删除会话" withArrow>
                    <span>
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="gray"
                        className="si-del"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(t.task_id);
                        }}
                      >
                        <IconTrash size={13} />
                      </ActionIcon>
                    </span>
                  </Tooltip>
                </Group>
              </button>
            ))}
          </div>
        ))}
      </ScrollArea>
    </div>
  );
}

// ===== 底部输入栏（Mantine Textarea + 按钮） =====
export function Composer(props: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  disabled: boolean;
  running: boolean;
  maxSteps: number;
  setMaxSteps: (n: number) => void;
  threadId: string;
  setThreadId: (s: string) => void;
}) {
  const {
    value,
    onChange,
    onSend,
    onStop,
    onKeyDown,
    disabled,
    running,
    maxSteps,
    setMaxSteps,
    threadId,
    setThreadId,
  } = props;

  return (
    <div className="composer">
      <Paper className="composer-box" radius="lg" withBorder p="sm">
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="给 Flare 发一个任务…"
          variant="unstyled"
          autosize
          minRows={1}
          maxRows={6}
          disabled={disabled}
        />
        <Group justify="space-between" mt={8}>
          <Text size="xs" c="dimmed" fz={11}>
            Enter 发送 · Shift+Enter 换行
          </Text>
          {running ? (
            <Button
              size="xs"
              variant="light"
              color="red"
              leftSection={<IconStop size={13} />}
              onClick={onStop}
            >
              停止
            </Button>
          ) : (
            <ActionIcon
              color="flare"
              variant="filled"
              size="lg"
              radius="md"
              disabled={disabled || !value.trim()}
              onClick={onSend}
              title="发送 (Enter)"
            >
              <IconSend size={15} />
            </ActionIcon>
          )}
        </Group>
      </Paper>
      <Group gap="lg" mt={8} justify="center" fz="xs" c="dimmed">
        <Group gap={6}>
          <Text size="xs" c="dimmed">
            最大步骤
          </Text>
          <NumberInput
            size="xs"
            min={1}
            max={50}
            value={maxSteps}
            onChange={(v) => setMaxSteps(typeof v === "number" ? v : 5)}
            disabled={disabled}
            w={70}
            hideControls
          />
        </Group>
        <Group gap={6}>
          <Text size="xs" c="dimmed">
            thread_id
          </Text>
          <TextInput
            size="xs"
            value={threadId}
            onChange={(e) => setThreadId(e.target.value)}
            placeholder="留空自动生成"
            disabled={disabled}
            w={180}
          />
        </Group>
      </Group>
    </div>
  );
}
