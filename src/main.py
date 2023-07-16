from typing import Literal, Union, NamedTuple
from enum import Enum


import discord
from discord import Message as DiscordMessage
import logging
from src.base import Message, Conversation
from src.constants import (
    PROMPT_LIST,
    PROMPT_NAME_FOR_ENUM,
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
    EXAMPLE_CONVOS,
    ACTIVATE_THREAD_PREFX,
    MAX_THREAD_MESSAGES,
    SECONDS_DELAY_RECEIVING_MSG,
)
import asyncio
from src.utils import (
    logger,
    should_block,
    close_thread,
    is_last_message_stale,
    discord_message_to_message,
)
from src import completion
from src.completion import generate_completion_response, process_response
from src.moderation import (
    moderate_message,
    send_moderation_blocked_message,
    send_moderation_flagged_message,
)

logging.basicConfig(
    format="[%(asctime)s] [%(filename)s:%(lineno)d] %(message)s", level=logging.INFO
)

intents = discord.Intents.default()
intents.messages = True

client = discord.Client(intents=intents)
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

CHOOSE_PROMPT = ''


@client.event
async def on_ready():
    logger.info(f"We have logged in as {client.user}. Invite URL: {BOT_INVITE_URL}")
    completion.MY_BOT_NAME = client.user.name
    await tree.sync()

# # /chat message:
# @tree.command(name="testing_method", description="Create a new thread for conversation",)
# @discord.app_commands.checks.has_permissions(send_messages=True)
# @discord.app_commands.checks.has_permissions(view_channel=True)
# @discord.app_commands.checks.bot_has_permissions(send_messages=True)
# @discord.app_commands.checks.bot_has_permissions(view_channel=True)
# @discord.app_commands.checks.bot_has_permissions(manage_threads=True)
# async def test_command(interaction: discord.Interaction):
#     await interaction.response.send_message(repr(fruit))

# /chat message:
@tree.command(name="chat", description="Create a new thread for conversation")
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(manage_threads=True)
async def chat_command(int: discord.Interaction, action: Enum('prompt', PROMPT_NAME_FOR_ENUM)):
    message = "chat-room"
    global CHOOSE_PROMPT
    CHOOSE_PROMPT= PROMPT_LIST[str(action)[7:]]
    await int.response.send_message(f'Prompt: {str(action)[7:]}\n')

    try:
        # only support creating thread in text channel
        if not isinstance(int.channel, discord.TextChannel):
            return

        # block servers not in allow list
        # if should_block(guild=int.guild):
        #     return

        user = int.user

        response = await int.original_response()
        # create the thread
        thread = await response.create_thread(
            name=f"{ACTIVATE_THREAD_PREFX} {user.name[:20]} - {message}",
            slowmode_delay=1,
            reason="gpt-bot",
            auto_archive_duration=60,
        )
        # async with thread.typing():
        #     # fetch completion
            
            
        #     messages = [Message(user="user", text=message)]
        #     # print("-----------------chat_command-------------------------------")
        #     # print(messages)
        #     # print("------------------------------------------------")
        #     response_data = await generate_completion_response(
        #         messages=messages, user=user, choose_prompt=CHOOSE_PROMPT
        #     )
        #     # send the result
        #     await process_response(
        #         user=user, thread=thread, response_data=response_data
        #     )
    except Exception as e:
        logger.exception(e)
        await int.response.send_message(
            f"Failed to start chat {str(e)}", ephemeral=True
        )


# calls for each message
@client.event
async def on_message(message: DiscordMessage):
    try:
        # block servers not in allow list
        # if should_block(guild=message.guild):
        #     return

        # ignore messages from the bot
        if message.author == client.user:
            return

        # ignore messages not in a thread
        channel = message.channel
        if not isinstance(channel, discord.Thread):
            return

        # ignore threads not created by the bot
        thread = channel
        if thread.owner_id != client.user.id:
            return

        # ignore threads that are archived locked or title is not what we want
        if (
            thread.archived
            or thread.locked
            or not thread.name.startswith(ACTIVATE_THREAD_PREFX)
        ):
            # ignore this thread
            return

        # if thread.message_count > MAX_THREAD_MESSAGES:
        #     # too many messages, no longer going to reply
        #     await close_thread(thread=thread)
        #     return

        # wait a bit in case user has more messages
        if SECONDS_DELAY_RECEIVING_MSG > 0:
            await asyncio.sleep(SECONDS_DELAY_RECEIVING_MSG)
            if is_last_message_stale(
                interaction_message=message,
                last_message=thread.last_message,
                bot_id=client.user.id,
            ):
                # there is another message, so ignore this one
                return

        logger.info(
            f"Thread message to process - {message.author}: {message.content[:50]} - {thread.name} {thread.jump_url}"
        )
        channel_messages = [
            discord_message_to_message(message)
            async for message in thread.history(limit=MAX_THREAD_MESSAGES)
        ]
        channel_messages = [x for x in channel_messages if x is not None]
        channel_messages.reverse()
        # generate the response
        async with thread.typing():
            global CHOOSE_PROMPT
            response_data = await generate_completion_response(
                messages=channel_messages, user=message.author, choose_prompt=CHOOSE_PROMPT
            )

        if is_last_message_stale(
            interaction_message=message,
            last_message=thread.last_message,
            bot_id=client.user.id,
        ):
            # there is another message and its not from us, so ignore this response
            return

        # send response
        await process_response(
            user=message.author, thread=thread, response_data=response_data
        )
    except Exception as e:
        logger.exception(e)


client.run(DISCORD_BOT_TOKEN)
