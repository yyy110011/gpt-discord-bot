from enum import Enum
from dataclasses import dataclass
import openai
from src.moderation import moderate_message
from typing import Optional, List
from src.constants import (
    BOT_INSTRUCTIONS,
    BOT_NAME,
    EXAMPLE_CONVOS,
)
import discord
from src.base import Message, Prompt, Conversation
from src.utils import split_into_shorter_messages, close_thread, logger
from src.moderation import (
    send_moderation_flagged_message,
    send_moderation_blocked_message,
)

MY_BOT_NAME = BOT_NAME
MY_BOT_EXAMPLE_CONVOS = EXAMPLE_CONVOS


class CompletionResult(Enum):
    OK = 0
    TOO_LONG = 1
    INVALID_REQUEST = 2
    OTHER_ERROR = 3
    MODERATION_FLAGGED = 4
    MODERATION_BLOCKED = 5


@dataclass
class CompletionData:
    status: CompletionResult
    reply_text: Optional[str]
    status_text: Optional[str]


async def generate_completion_response(
    messages: List[Message], user: str, choose_prompt: str
) -> CompletionData:
    try:
        prompt = Prompt(
            header=Message(
                "system", choose_prompt
            ),
            convo=Conversation(messages),
        )
        rendered = prompt.render()
        # print(messages[-1].)
        # rendered = [
        #     {"role": "user", "content": messages[-1].render()}
        # ]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=rendered
        )
        # "choices"][0]["delta"]["content"]
        reply = response["choices"][0]["message"]["content"] #response.choices[0].text.strip()
        # if reply:
        #     # flagged_str, blocked_str = moderate_message(
        #     #     message=(rendered + reply)[-500:], user=user
        #     # )
        #     if len(blocked_str) > 0:
        #         return CompletionData(
        #             status=CompletionResult.MODERATION_BLOCKED,
        #             reply_text=reply,
        #             status_text=f"from_response:{blocked_str}",
        #         )

        #     if len(flagged_str) > 0:
        #         return CompletionData(
        #             status=CompletionResult.MODERATION_FLAGGED,
        #             reply_text=reply,
        #             status_text=f"from_response:{flagged_str}",
        #         )

        return CompletionData(
            status=CompletionResult.OK, reply_text=reply, status_text=None
        )
    except openai.error.InvalidRequestError as e:
        if "This model's maximum context length" in e.user_message:
            return CompletionData(
                status=CompletionResult.TOO_LONG, reply_text=None, status_text=str(e)
            )
        else:
            logger.exception(e)
            return CompletionData(
                status=CompletionResult.INVALID_REQUEST,
                reply_text=None,
                status_text=str(e),
            )
    except Exception as e:
        logger.exception(e)
        return CompletionData(
            status=CompletionResult.OTHER_ERROR, reply_text=None, status_text=str(e)
        )

async def generate_compress_completion_response(
    messages: List[Message], user: str, choose_prompt: str
) -> CompletionData:
    print("-----> Do compressing")
    try:
        messages.append(
            Message(
                "user", "Please summarize the conversation above, into a set of user and assistant conversations (less than 5) include code blocks. PLEASE DO NOT INCLUDE ANY GREETING MESSAGES."
            )
        )
        prompt = Prompt(
            header=Message(
                "system", choose_prompt
            ),
            convo=Conversation(messages),
        )
        rendered = prompt.render()
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=rendered
        )

        reply = response["choices"][0]["message"]["content"] #response.choices[0].text.strip()
        print(reply)
        return CompletionData(
            status=CompletionResult.OK, reply_text=reply, status_text=None
        )
    except openai.error.InvalidRequestError as e:
        if "This model's maximum context length" in e.user_message:
            return CompletionData(
                status=CompletionResult.TOO_LONG, reply_text=None, status_text=str(e)
            )
        else:
            logger.exception(e)
            return CompletionData(
                status=CompletionResult.INVALID_REQUEST,
                reply_text=None,
                status_text=str(e),
            )
    except Exception as e:
        logger.exception(e)
        return CompletionData(
            status=CompletionResult.OTHER_ERROR, reply_text=None, status_text=str(e)
        )

async def process_response(
    user: str, thread: discord.Thread, response_data: CompletionData
):
    status = response_data.status
    reply_text = response_data.reply_text
    status_text = response_data.status_text
    if status is CompletionResult.OK or status is CompletionResult.MODERATION_FLAGGED:
        sent_message = None
        if not reply_text:
            sent_message = await thread.send(
                embed=discord.Embed(
                    description=f"**Invalid response** - empty response",
                    color=discord.Color.yellow(),
                )
            )
        else:
            shorter_response = split_into_shorter_messages(reply_text)
            for r in shorter_response:
                sent_message = await thread.send(r)
        if status is CompletionResult.MODERATION_FLAGGED:
            await send_moderation_flagged_message(
                guild=thread.guild,
                user=user,
                flagged_str=status_text,
                message=reply_text,
                url=sent_message.jump_url if sent_message else "no url",
            )

            await thread.send(
                embed=discord.Embed(
                    description=f"⚠️ **This conversation has been flagged by moderation.**",
                    color=discord.Color.yellow(),
                )
            )
    elif status is CompletionResult.MODERATION_BLOCKED:
        await send_moderation_blocked_message(
            guild=thread.guild,
            user=user,
            blocked_str=status_text,
            message=reply_text,
        )

        await thread.send(
            embed=discord.Embed(
                description=f"❌ **The response has been blocked by moderation.**",
                color=discord.Color.red(),
            )
        )
    elif status is CompletionResult.TOO_LONG:
        await close_thread(thread)
    elif status is CompletionResult.INVALID_REQUEST:
        await thread.send(
            embed=discord.Embed(
                description=f"**Invalid request** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
    else:
        await thread.send(
            embed=discord.Embed(
                description=f"**Error** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
