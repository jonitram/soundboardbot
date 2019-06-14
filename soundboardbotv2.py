import discord
import asyncio
import pafy
from pydub import AudioSegment
import multiprocessing
import random
import os
import sys

# api tokens
discord_token=None
youtube_token=None

# the text file that the tokens are stored in
tokensfile = "tokens.txt"

# the message prefix required to call the bot in discord
command_prefix = '.sbb'
# the filename prefix for audio files related to the bot
file_prefix = '.sbb'
# the filetype for audio files downloaded for commands
file_suffix = '.mp3'
# audio commands
audio_commands = []
# other commands sorted in alphabetical order
other_commands = ['clear','copy','create','delete','help','listaudio','random','remove']
# all commands
commands = []

# cleaning up bot messages is set to off by default
delete_msgs = False
# video duration limit for time constraint purposes (in minutes)
duration_limit = 180
# list of commands that are currently being created
# <logic>: basically check for the existence of a file in the cwd and if it exists
# then the command can be removed from this list
downloading = []
# maximum number of commands allowed
command_limit = 50


# sets up both discord_token and youtube_token by reading them from filename
def setup_tokens(filename):
    global discord_token, youtube_token
    tokens = open(filename, "r")
    discord_token = tokens.readline().rstrip()
    youtube_token = tokens.readline().rstrip()
    tokens.close()

# builds a list of audio commands from existing files already created
def build_commands():
    result = []
    for filename in os.listdir(os.getcwd()):
        if filename.startswith(file_prefix) and filename.endswith(file_suffix):
            result.append(filename[4:-4])
    result.sort()
    return result

# setup the master list of all callable commands
def setup_commands():
    audio_commands = build_commands()
    commands = audio_commands + other_commands

# todo list: add asynchronous downloading so the bot doesnt crash, add being able to quit in the middle of playing
# duration of video has to be greater than 5 seconds

#@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

#@client.event
async def on_message(message):
    if message.author.bot:
        global delete_msgs 
        if delete_msgs and message.content.lower().startswith(command_prefix):
            await delete_command(message)
        return
    elif message.content.lower().startswith(command_prefix):
        global commands
        global voice_commands
        author_mention = message.author.mention
        command = message.content[5:]
        if command.startswith('create '):
            msg_split = message.content.split(" ")
            if len(msg_split) != 6:
                error_msg = 'That is not the correct \"create\" voice command formatting! ' + author_mention
                await check_send_msg(message, error_msg)
                return
            await create_command(message, msg_split[2], msg_split[3], msg_split[4], msg_split[5])
            return
        elif command.startswith('remove '):
            msg_split = message.content.split(" ")
            if len(msg_split) != 3:
                error_msg = 'That is not the correct \"remove\" command formatting! ' + author_mention
                await check_send_msg(message, error_msg)
                return
            voice_command = msg_split[2]
            if voice_command not in voice_commands:
                error_msg = 'That voice command does not exist! ' + author_mention
                await check_send_msg(message, error_msg)
                return
            elif remove_command(voice_command):
                update = 'The ' + command_prefix + voice_command + ' voice command has been deleted. ' + author_mention
                await check_send_msg(message, update)
                voice_commands.remove(voice_command)
                commands.remove(voice_command)
                if delete_msgs:
                    await delete_command(message)
                return
            else:
                error_msg = 'The requested voice command\'s file could not be found!' + author_mention
                await check_send_msg(message, error_msg)
                return
        elif command.startswith('copy '):
            msg_split = message.content.split(" ")
            if len(msg_split) != 3 or len(message.attachments) == 0:
                error_msg = 'That is not the correct \"copy\" command formatting! ' + author_mention
                await check_send_msg(message, error_msg)
                return
            await copy_command(message, msg_split[2])
            return
        elif command == 'listvoice':
            msg = list_voice_commands(author_mention)
            await check_send_msg(message, msg)
            if delete_msgs:
                await delete_command(message)
            return
        elif command == 'delete':
            delete_msgs = not delete_msgs
            await send_delete_update(message)
            return
        elif command == 'clear':
            await clear(message)
            return
        elif command == 'help':
            await send_help(message)
            if delete_msgs:
                await delete_command(message)
            return
        elif command not in commands:
            error_msg = 'That is not a valid command! ' + author_mention
            await check_send_msg(message, error_msg)
            return
        elif message.author.voice_channel is None:
            error_msg = 'You (' + author_mention + ') need to be in a voice channel to use that command!'
            await check_send_msg(message, error_msg)
            return
        await execute(message)
        if delete_msgs:
            await delete_command(message)
    return

def list_voice_commands(author):
    result = author + ' Here is a list of voice commands: '
    if len(voice_commands) > 0:
        for command in voice_commands:
            result += command + ', '
        result += ' and random.'
    else:
        result += 'There are no voice commands yet!'
    return result

def remove_command(voice_command):
    file_name = file_prefix + voice_command + file_suffix
    if file_name in os.listdir(os.getcwd()):
        os.remove(file_name)
        return True
    return False

async def execute(message):
    voice_channel = message.author.voice_channel
    me_as_member = message.channel.server.me
    if voice_channel.permissions_for(me_as_member).speak:
        command = message.content[5:]
        file = get_sound(command)
        if file != 'error':
            voice = await client.join_voice_channel(voice_channel)
            player = voice.create_ffmpeg_player(file)
            player.start()
            while True:
                if not player.is_playing():
                    await voice.disconnect()
                    return
        return
    author_mention = message.author.mention
    self_mention = client.user.mention
    error_msg = self_mention + ' cannot speak in your voice channel! ' + author_mention
    await check_send_msg(message, error_msg)
    return

def get_sound(command):
    if command == 'random':
        result = file_prefix + random.choice(voice_commands) + file_suffix
        return result
    elif command in voice_commands:
        result = file_prefix + command + file_suffix
    else: 
        result = 'error'
    return result

async def send_help(message):
    me_as_member = message.channel.server.me
    author_mention = message.author.mention
    self_mention = client.user.mention
    msg = author_mention + ' Issue a command by typing \"' + command_prefix + ' \" followed by the command to execute it.\n'
    msg += 'Use the \"delete\" command " to toggle deleting valid issued commands.\n'
    msg += 'Mass remove valid and invalid commands made to ' + self_mention + ' and messages sent by ' + self_mention + ' (up to 500 messages back) with the \"clear\" command.\n'
    msg += list_voice_commands('') + '\n'
    msg += 'You must be in a voice channel to use a voice command.\n'
    msg += 'Create a voice command using the \"create\" command followed by \" <YouTubeURL> <CommandName> <StartTime(Min:Sec)> <Duration(Sec)>\" with each seperated by a single space.\n' 
    msg += 'Turn your own sound file into a command using the \"copy\" command followed by \" <CommandName>\" and uploading the single sound file attached to the message.'
    msg += 'Uploaded sound files can be no longer than 20 seconds.\n'
    msg += 'Remove a voice command by using the \"remove \" command followed by the command name.\n'
    msg += 'To list the voice commands available, use the \"listvoice\" command.\n'
    msg += 'Finally, to resend this message use the \"help\" command.'
    await check_send_msg(message, msg)
    return

async def clear(message):
    deleted = 0
    me_as_member = message.channel.server.me
    if message.channel.permissions_for(me_as_member).manage_messages:
        deleted = await client.purge_from(message.channel, limit=500, check=clear_conditions)
    else:
        self_mention = client.user.mention
        error_msg = self_mention + ' does not have permission to remove messages! ' + author_mention
        await check_send_msg(message, error_msg)
    await client.send_message(message.channel, 'Deleted {} message(s).'.format(len(deleted)))
    return

def clear_conditions(message):
    msg = message.content.lower()
    return message.author == client.user or msg.startswith(command_prefix) #and msg[5:] in commands

async def delete_command(message):
    me_as_member = message.channel.server.me
    if message.channel.permissions_for(me_as_member).manage_messages:
        await client.delete_message(message)
    else:
        self_mention = client.user.mention
        error_msg = self_mention + ' does not have permission to remove messages! ' + author_mention
        await check_send_msg(message, error_msg)
    return

async def send_delete_update(message):
    author_mention = message.author.mention
    if delete_msgs:
       delete_update = 'Valid commands will now be deleted if possible. ' + author_mention
       await check_send_msg(message, delete_update)
       await delete_command(message)
    else:
       delete_update = 'Commands will no longer be deleted. ' + author_mention
       await check_send_msg(message, delete_update)
    return

async def copy_command(message, command_name):
    if command_name in commands:
        error_msg = 'That command is already defined! If it is a voice command, please delete that voice command first! ' + author_mention
        await check_send_msg(message, error_msg)
        return
    elif len(commands) > command_limit:
        error_msg = 'There are already ' + str(command_limit) + ' commands! Please remove a command before adding a new one. ' + author_mention
        await check_send_msg(message, error_msg)
        return
    if len(message.attachments) == 1:
        await message.attachments[0].get(message.attachments[0].filename).save()
        audio = AudioSegment.from_file(message.attachments[0].filename)
        if audio.duration_seconds > 20:
            os.remove(message.attachments[0].filename)
            error_msg = 'That sound file is too long!' + author_mention
            await check_send_msg(message, error_msg)
            return
        file_name = file_prefix + command_name + file_suffix
        audio.export(file_name, format=formatting)
        voice_commands.append(command_name)
        voice_commands.sort()
        os.remove(message.attachments[0].filename)
    return

async def create_command(message, url, command_name, start_time, duration):
    streams = pafy.new(url)
    author_mention = message.author.mention
    if command_name in commands:
        error_msg = 'That command is already defined! If it is a voice command, please delete that voice command first! ' + author_mention
        await check_send_msg(message, error_msg)
        return
    if download_preconditions(streams) == 1:
        error_msg = 'That YouTube video is too long! Please limit requested videos to ' + str(video_limit) + ' minutes or less in length. ' + author_mention
        await check_send_msg(message, error_msg)
        return
    elif download_preconditions(streams) == 2:
        error_msg = 'There are already ' + str(command_limit) + ' commands! Please remove a command before adding a new one. ' + author_mention
        await check_send_msg(message, error_msg)
        return
    audio_list = streams.m4astreams
    best_audio_index = len(audio_list) - 1
    best_audio = audio_list[best_audio_index]
    update = author_mention + ' downloading the requested video!'
    await check_send_msg(message, update)
    best_audio.download()
    update = author_mention + ' download complete! Beginning trimming audio.'
    title = streams.title + '.m4a'
    stream_length = streams.length
    next_action = asyncio.ensure_future(trim_audio(message, title, stream_length, start_time, duration, command_name))
    if next_action == 1:
        error_msg = 'That is not the correct starting time format! Please use <Minutes>:<Seconds>! ' + author_mention
        await check_send_msg(message, error_msg)
        return
    elif next_action == 2:
        error_msg = 'Duration must be greater than 0! ' + author_mention
        await check_send_msg(message, error_msg)
        return
    elif next_action == 3:
        error_msg = 'The starting time must be greater than or equal to 0:00! ' + author_mention
        await check_send_msg(message, error_msg)
        return
    elif next_action == 4:
        error_msg = 'The starting time must be within the video\'s length! ' + author_mention
        await check_send_msg(message, error_msg)
        return
    elif next_action == 5:
        error_msg = 'You cannot have the duration extend passed the end of the video! ' + author_mention
        await check_send_msg(message, error_msg)
        return
    return

async def trim_audio(message, title, length, start_time, duration, command_name):
    times = start_time.split(':')
    formatting = file_suffix[1:]
    if len(times) != 2:
        return 1
    elif float(duration) <= 0:
        return 2
    total_start_time = (float(times[0]) * 60) + float(times[1])
    if total_start_time < 0:
        return 3
    audio = AudioSegment.from_file(title,'m4a')
    audio_length = audio.duration_seconds
    print('original video length = ' + str(length))
    print('original audio length = ' + str(audio_length))
    # add 1 to length to account for milliseconds
    if (length + 1) < audio_length:
        audio_length /= 2
    print('updated audio length = ' + str(audio_length))
    video_limit_sec = video_limit * 60
    if total_start_time >= audio_length:
        return 4
    elif total_start_time + float(duration) > audio_length:
        return 5
    start_time_ms = (audio_length - total_start_time) * -1000
    print('start time ms = '+str(start_time_ms))
    duration_ms = float(duration) * 1000
    print('duration ms  = '+ str(duration_ms))
    starting_audio = audio[start_time_ms:]
    final_audio = starting_audio[:duration_ms]
    file_name = file_prefix + command_name + file_suffix
    final_audio.export(file_name, format=formatting)
    os.remove(title)
    voice_commands.append(command_name)
    voice_commands.sort()
    commands.append(command_name)
    voice_commands.sort()
    author_mention = message.author.mention
    update = author_mention + ' trimming complete! ' + command_prefix + command_name + ' is now ready to be used!'
    await check_send_msg(message, update)
    return 0

def download_preconditions(streams):
    video_limit_sec = video_limit * 60
    if streams.length > video_limit_sec:
       return 1
    if len(commands) > command_limit:
        return 2
    return 0

async def check_send_msg(message, message_content):
    me_as_member = message.channel.server.me
    if message.channel.permissions_for(me_as_member).send_messages:
        await client.send_message(message.channel, message_content)
    return

# main function
def main():
    setup_tokens(tokensfile)
    setup_commands()
    client = discord.Client()
    pafy.set_api_key(youtube_token)
    client.run(discord_token)

if __name__ == "__main__": main()

