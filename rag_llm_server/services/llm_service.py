import os
from volcenginesdkarkruntime import Ark 
from config import settings

class LLMService:
    def __init__(self):
        self.client = None

    def _get_client(self):
        """Create the Ark client only when a model request is actually made."""
        if not settings.ARK_API_KEY:
            return None

        if self.client is None:
            self.client = Ark(
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                api_key=settings.ARK_API_KEY,
                timeout=1800,
            )

        return self.client

    def chat_stream(self, history_messages: list, rag_context: str = ""):
        """
        流式对话
        :param history_messages: 对话历史
        :param rag_context: 从 rag_service 检索出来的背景知识
        """
        client = self._get_client()
        if client is None:
            print("❌ LLM 配置缺失: 请在 .env 中设置 ARK_API_KEY")
            yield None
            return

        # --- 1. 定义课程顾问的系统提示词 ---
        system_content = """
        # 角色
        你是【懂小智】，AI 课程顾问。你的表达专业、简洁、有行动感，适合实时语音对话。

        # 核心任务
        1. 只依据【参考知识库】回答课程、学习路线和项目相关问题。
        2. 优先给出直接结论，再补充一至三个关键依据。
        3. 知识库没有覆盖时，明确说明资料不足，并建议联系人工老师确认。

        # 行为准则
        - 默认使用中文，控制在 2 至 5 句，避免长篇复述知识库。
        - 不编造价格、优惠、开班日期、合同、退款规则或课程内容。
        - 不承诺就业、薪资、面试结果或个人职业结果。
        - 不索要密码、API Key、Secret Key 等敏感凭证。
        - 不使用侮辱、贬低、施压或过度营销的话术。
        - 用户问题超出资料范围时，不把推测包装成确定事实。
                """.strip()

        # --- 2. 构造最终发送给模型的消息序列 ---
        # messages = [{"role": "system", "content": system_content}]

        system_blocks = [system_content]

        if rag_context:
            # 使用明确的定界符，帮助模型在毫秒内定位知识
            system_blocks.append(f"### 参考知识库（绝对准则）\n{rag_context.strip()}")

        # 合并为一条
        final_system_prompt = "\n\n".join(system_blocks)

        # 最终的消息序列
        messages = [{"role": "system", "content": final_system_prompt}]

        # 加入历史对话（确保包含用户最新的问题）
        messages.extend(history_messages)

        try:
            print(f"🚀 发起流式调用 (Endpoint: {settings.ARK_ENDPOINT_ID})")
            
            stream = client.chat.completions.create(
                model=settings.ARK_ENDPOINT_ID,
                messages=messages,
                temperature=0.3, # 降低随机性，确保回答更严谨地贴合 RAG
                # 实时语音对首包延迟非常敏感；课程问答不需要
                # 长链路推理，因此显式关闭深度思考。
                thinking={"type": "disabled"},
                stream=True,
                stream_options={"include_usage": True},
            )

            for chunk in stream:
                yield chunk

        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            yield None

llm_service = LLMService()
