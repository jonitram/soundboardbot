#!/usr/bin/env python3
import discord
import asyncio
import pafy
from pydub import AudioSegment
import multiprocessing
import random
import os
import sys

# TODO:
# UPDATE README WITH BOT INSTRUCTIONS
# maybe copy help message / put call .sbb help to let people know how
# to use it
# add user prompt for if tokens.txt exists and if they would like to reset it or not
# maybe change finished from a list to a value/queue
# duration of video has to be greater than 5 seconds <- TEST THIS
# FINISH COPY - using message -> save('filename')

# multiprocessing shared list
mpmanager = multiprocessing.Manager()

# api tokens
discord_token=None
youtube_token=None

# the discord client
client = discord.Client()

# the text file that the tokens are stored in
tokensfile = "tokens.txt"

# the message prefix required to call the bot in discord
command_prefix = '.sbb'
# the filename prefix for audio files related to the bot
file_prefix = 'sbb_'
# the filetype for audio files downloaded for commands
file_suffix = '.mp3'
# audio commands
audio_commands = []
# other commands sorted in alphabetical order
other_commands = ['cleanup','clear','create','downloading','help','listaudio','stop','random','remove']
# all commands
commands = []

# cleaning up bot messages is set to off by default
cleanup = False

# create preconditions
# max creates sound duration limit for time constraint purposes (in seconds)
duration_limit = 30
# video length limit (in minutes, currently 45)
video_length_limit = 45 * 60
# list of commands that are currently being created
downloading = []
# number of concurrent downloads allowed
downloading_limit = 1
# list of finished downloaded commands
finished = mpmanager.list()
# maximum number of commands allowed
command_limit = 100

# current audio player for disconnecting through stop
audio_player = None
# current audio task for cancelling throuhg stop
audio_task = None

# initialization stuff
# sets up both discord_token and youtube_token by reading them from filename
def setup_tokens(filename):
    global discord_token, youtube_token
    tokens = open(filename, "r")
    discord_token = tokens.readline().rstrip()
    youtube_token = tokens.readline().rstrip()
    tokens.close()
    return

# builds a list of audio commands from existing files already created
def build_commands():
    result = []
    for filename in os.listdir(os.getcwd()):
        if filename.startswith(file_prefix) and filename.endswith(file_suffix):
            result.append(filename[len(file_prefix):-len(file_suffix)])
    result.sort()
    return result

# setup the master list of all callable commands
def setup_commands():
    global audio_commands, commands
    audio_commands = build_commands()
    commands = audio_commands + other_commands
    return

@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

@client.event
async def on_message(message):
    global finished, downloading, audio_commands, commands
    if message.content.lower().startswith(command_prefix):
        asyncio.create_task(filter_message(message))
        if cleanup:
            asyncio.create_task(delete_message(message))
    return  

async def filter_message(message):
    global audio_task, audio_player
    author_mention = message.author.mention
    command = message.content[5:]
    parameters = command.split(' ')
    if parameters[0] == 'create':
        if len(parameters) != 5:
            error_message = author_mention + ' That is not the correct \"create\" audio command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            asyncio.create_task(create_command(message, parameters[1], parameters[2], parameters[3], parameters[4]))
            return
    elif parameters[0] == 'remove':
        if len(parameters) != 2:
            error_message = author_mention + ' That is not the correct \"remove\" audio command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            asyncio.create_task(remove_command(message, parameters[1]))
            return
    elif parameters[0] == 'listaudio':
        asyncio.create_task(send_list_audio_commands(message))
        return
    elif parameters[0] == 'cleanup':
        asyncio.create_task(cleanup_update(message))
        return
    elif parameters[0] == 'clear':
        asyncio.create_task(clear(message))
        return
    elif parameters[0] == 'help':
        asyncio.create_task(send_help(message))
        return
    elif parameters[0] == 'downloading':
        asyncio.create_task(send_downloading(message))
        return
    elif parameters[0] == 'stop':
        await stop_command(message)
        return
    elif command not in commands:
        error_message = author_mention + ' That is not a valid command!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif message.author.voice is None:
        error_message = author_mention + ' You need to be in a audio channel to use that command!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    else:
        if audio_task != None and audio_task.done():
            audio_task = None
        if audio_task == None:
            audio_task = asyncio.create_task(execute_audio_command(message))  
        else:
            error_message = author_mention + ' An audio command is currently playing. Please wait for it to finish or use the \"stop\" command before playing a new one.'
            asyncio.create_task(check_send_message(message, error_message))
        return

async def stop_command(message):
    global audio_task, audio_player
    author_mention = message.author.mention
    me_as_member = message.channel.guild.me
    if message.author.voice != None:
        if me_as_member.voice != None:
            if message.author.voice.channel == me_as_member.voice.channel:
                if audio_task != None:
                    audio_task.cancel()
                    result = author_mention + ' The currently playing audio command has stopped.'
                    await audio_player.disconnect()
                    audio_player = None
                    audio_task = None
                else:
                    print('***Concurrency Error, should not be possible***')
            else:
                result = author_mention + ' You have to be in the same voice channel as the bot to use the \"stop\" command.'
        else:
            result = author_mention + ' There is no audio command currently playing.'
    else:
        result = author_mention + ' You have to be in a voice channel to use the \"stop\" command.'
    asyncio.create_task(check_send_message(message, result))
    return

async def clear(message):
    deleted = 0
    author_mention = message.author.mention
    me_as_member = message.channel.guild.me
    if message.channel.permissions_for(me_as_member).manage_messages:
        deleted = await message.channel.purge(limit=500, check=clear_conditions)
    else:
        self_mention = client.user.mention
        error_message = author_mention + ' ' + self_mention + ' does not have permission to remove messages! '
        asyncio.create_task(check_send_message(message, error_message))
    asyncio.create_task(message.channel.send('Deleted {} message(s).'.format(len(deleted))))
    return

def clear_conditions(message):
    current_message = message.content.lower()
    return message.author == client.user or current_message.startswith(command_prefix)

async def cleanup_update(message):
    global cleanup
    author_mention = message.author.mention
    cleanup = not cleanup
    if cleanup:
       cleanup_update_message = author_mention + ' any messages beginning with the \".sbb\" command prefix will now be deleted, if possible.'
       asyncio.create_task(check_send_message(message, cleanup_update_message))
    else:
       cleanup_update_message = author_mention + ' Commands will no longer be deleted.'
       asyncio.create_task(check_send_message(message, cleanup_update_message))
    return

async def remove_command(message, audio_command):
    global audio_commands, commands
    author_mention = message.author.mention
    if audio_command not in audio_commands:
        error_message = author_mention + ' That audio command does not exist!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif remove_audio_file(audio_command):
        update = author_mention + ' The ' + command_prefix + ' ' + audio_command + ' audio command has been removed.'
    else:
        update = author_mention + ' The requested audio command\'s file could not be found! The ' + audio_command + ' audio command has been removed.'
    audio_commands.remove(audio_command)
    commands.remove(audio_command)
    asyncio.create_task(check_send_message(message, update))
    return
        
def remove_audio_file(audio_command):
    file_name = file_prefix + audio_command + file_suffix
    if file_name in os.listdir(os.getcwd()):
        os.remove(file_name)
        return True
    return False

async def send_downloading(message):
    author_mention = message.author.mention
    list_downloads = author_mention + ' ' + list_downloading()
    asyncio.create_task(check_send_message(message, list_downloads))
    return

def list_downloading():
    result = 'Here is a list of all currently downloading commands: '
    if len(downloading) > 0:
        for command in downloading:
            result += command + ' '
    else:
        result += 'No commands are currently downloading!'
    return result

async def send_list_audio_commands(message):
    author_mention = message.author.mention
    list_audio_message = author_mention + ' ' + list_audio_commands()
    asyncio.create_task(check_send_message(message, list_audio_message))
    return

def list_audio_commands():
    result = 'Here is a list of audio commands: '
    if len(audio_commands) > 0:
        for command in audio_commands:
            result += command + ', '
        result += ' and random.'
    else:
        result += 'There are no audio commands yet!'
    return result

async def execute_audio_command(message):
    global audio_player
    audio_channel = message.author.voice.channel
    me_as_member = message.channel.guild.me
    author_mention = message.author.mention
    if audio_channel.permissions_for(me_as_member).speak:
        command = message.content[5:]
        file = get_sound(command)
        if file != None:
            audio_player = await audio_channel.connect()
            audio_player.play(discord.FFmpegPCMAudio(file), after=None)
            while audio_player.is_playing():
                await asyncio.sleep(1)
            audio_player.stop()
            await audio_player.disconnect()
            audio_player = None
        else:
            await remove_command(message, command)
        return
    self_mention = client.user.mention
    error_message = author_mention + ' ' + self_mention + ' cannot speak in your audio channel!'
    await check_send_message(message, error_message)
    return

def get_sound(command):
    if command == 'random':
        result = file_prefix + random.choice(audio_commands) + file_suffix
        return result
    elif command in audio_commands:
        result = file_prefix + command + file_suffix
    else: 
        result = None
    return result

async def send_help(message):
    author_mention = message.author.mention
    self_mention = client.user.mention
    help_message = author_mention + ' Issue a command by typing \"' + command_prefix + ' \" followed by the command to execute it.\n'
    help_message += 'Use the \"cleanup\" command " to toggle deleting commands issued to the bot.\n'
    help_message += 'Mass remove commands issued to the ' + self_mention + ' and messages sent by ' + self_mention + ' (up to 500 messages back) with the \"clear\" command.\n'
    help_message += list_audio_commands() + '\n'
    help_message += 'You must be in an audio channel to use an audio command.\n'
    help_message += 'To stop a currently playing audio command, use the \"stop\" command.'
    help_message += 'Create an audio command using the \"create\" command followed by \" <YouTubeURL> <CommandName> <StartTime(Min:Sec)> <Duration(Sec)>\" with each seperated by a single space.\n' 
    help_message += 'Use the \"downloading\" command to list all of the commands currently downloading.\n'
    # help_message += 'Turn your own sound file into a command using the \"copy\" command followed by \" <CommandName>\" and uploading the single sound file attached to the message.'
    # help_message += 'Uploaded sound files can be no longer than 20 seconds.\n'
    help_message += 'Remove an audio command by using the \"remove \" command followed by a space and the the command name.\n'
    help_message += 'To list the audio commands available, use the \"listaudio\" command.\n'
    help_message += 'Finally, to resend this message use the \"help\" command.'
    asyncio.create_task(check_send_message(message, help_message))
    return

async def delete_message(message):
    me_as_member = message.channel.guild.me
    author_mention = message.author.mention
    if message.channel.permissions_for(me_as_member).manage_messages:
        asyncio.create_task(message.delete())
    else:
        self_mention = client.user.mention
        error_message = author_mention + ' ' + self_mention + ' does not have permission to remove messages!'
        asyncio.create_task(check_send_message(message, error_message))
    return

def check_create_preconditions(url, command_name, start_time, duration):
    result = None
    video = pafy.new(url)
    min_and_seconds = start_time.split(':')
    if len(min_and_seconds) != 2:
        result = 'That is not the correct starting time format! Please use <Minutes>:<Seconds>!'
        return result
    start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
    if command_name in commands:
        result = 'That command is already defined! If it is a audio command, please delete that audio command first!'
    elif video.length > video_length_limit:
        result = 'That video would take too long to download, find a shorter video (' + video_length_limit + ' min or less).'
    elif command_name in downloading:
        result = 'That command is currently downloading. Please label your command something else.'
    elif len(commands) > command_limit:
        result = 'There are already ' + str(command_limit) + ' commands! Please remove a command before adding a new one.'
    elif float(duration) <= 0:
        result = 'Duration must be greater than 0!'
    elif float(duration) > duration_limit:
        result = 'Duration is far too long! Nobody wants to listen to your command drone on forever.'
    elif start_time_seconds <= 0:
        result = 'The starting time must be greater than or equal to 0:00 (You can use 0:00.1)'
    elif start_time_seconds >= video.length:
        result = 'The starting time must be within the video\'s length!'
    elif start_time_seconds + float(duration) > video.length:
        result = 'You cannot have the duration extend passed the end of the video!'
    elif len(downloading) >= downloading_limit:
        result = 'Too many commands being created at once! Please wait for another command to finish before creating a new one!'
    return result

async def create_command(message, url, command_name, start_time, duration):
    global downloading
    author_mention = message.author.mention
    create_preconditions = check_create_preconditions(url, command_name, start_time, duration)
    if create_preconditions != None:
        error_message = author_mention + ' ' + create_preconditions
        asyncio.create_task(check_send_message(message, error_message))
        return
    downloading.append(command_name)
    create_new_command_process = multiprocessing.Process(target=create_new_command, args=(url, command_name, start_time, duration))
    create_new_command_process.start()
    update = author_mention + ' Beginning to create the \"' + command_name + '\" command!'
    asyncio.create_task(check_send_message(message, update))
    asyncio.create_task(finished_command(message))
    return

async def finished_command(message):
    global finished, downloading, audio_commands, commands
    while len(finished) == 0:
        await asyncio.sleep(1)
    command = finished[0]
    finished.remove(command)
    result = 'This command has finished downloading: '
    result += command
    downloading.remove(command)
    audio_commands.append(command)
    audio_commands.sort()
    commands.append(command)
    commands.sort()
    asyncio.create_task(check_send_message(message, result))
    return

def create_new_command(url, command_name, start_time, duration):
    global finished
    video = pafy.new(url)
    video_formatting = 'm4a'
    download_video_process = multiprocessing.Process(target=download_video, args=(video, video_formatting))
    download_video_process.start()
    download_video_process.join()
    min_and_seconds = start_time.split(':')
    start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
    trim_and_create_process = multiprocessing.Process(target=trim_and_create, args=(video, video_formatting, command_name, start_time_seconds, duration))
    trim_and_create_process.start()
    trim_and_create_process.join()
    finished.append(command_name)
    return

def download_video(video, video_formatting):
    best_audio = video.getbestaudio(preftype=video_formatting)
    best_audio.download()
    return

def trim_and_create(video, video_formatting, command_name, start_time_seconds, duration_seconds):
    formatting = file_suffix[1:]
    video_file = video.title + '.' + video_formatting
    video_audio = AudioSegment.from_file(video_file,video_formatting)
    audio_length = video_audio.duration_seconds
    # PRINT STATEMENTS ARE JUST FOR DEBUGGING
    print('DEBUGGING WEIRD PAFY AUDIO LENGTH BUG (sometimes downloaded audio would be doubled in length with the latter half being silence')
    print('original video length = ' + str(video.length))
    print('original audio length = ' + str(audio_length))
    if (video.length + 1) < audio_length:
        audio_length /= 2
    print('updated audio length = ' + str(audio_length))
    start_time_ms = (audio_length - start_time_seconds) * -1000
    duration_ms = float(duration_seconds) * 1000
    print('start time in seconds = ' + str(start_time_seconds))
    print('start time in ms = ' + str(start_time_ms))
    print('duration in seconds = ' + str(duration_seconds))
    print('duration in ms = ' + str(duration_ms))
    starting_audio = video_audio[start_time_ms:]
    final_audio = starting_audio[:duration_ms]
    file_name = file_prefix + command_name + file_suffix
    final_audio.export(file_name, format=formatting)
    os.remove(video_file)
    return

async def check_send_message(message, message_content):
    me_as_member = message.channel.guild.me
    if message.channel.permissions_for(me_as_member).send_messages:
        await message.channel.send(message_content)
    return

# old implementation stuff for copy, not really sure what the top cleanup stuff is for 
# if message.author.bot:
#     global cleanup 
#     if cleanup and message.content.lower().startswith(command_prefix):
#         await delete_message(message)
#     return
#     elif command.startswith('copy '):
#         msg_split = message.content.split(" ")
#         if len(msg_split) != 3 or len(message.attachments) == 0:
#             error_message = 'That is not the correct \"copy\" command formatting! ' + author_mention
#             await check_send_message(message, error_message)
#             return
#         await copy_command(message, msg_split[2])
#         return

# async def copy_command(message, command_name):
#     if command_name in commands:
#         error_message = 'That command is already defined! If it is a audio command, please delete that audio command first! ' + author_mention
#         await check_send_message(message, error_message)
#         return
#     elif len(commands) > command_limit:
#         error_message = 'There are already ' + str(command_limit) + ' commands! Please remove a command before adding a new one. ' + author_mention
#         await check_send_message(message, error_message)
#         return
#     if len(message.attachments) == 1:
#         await message.attachments[0].get(message.attachments[0].filename).save()
#         audio = AudioSegment.from_file(message.attachments[0].filename)
#         if audio.duration_seconds > 20:
#             os.remove(message.attachments[0].filename)
#             error_message = 'That sound file is too long!' + author_mention
#             await check_send_message(message, error_message)
#             return
#         file_name = file_prefix + command_name + file_suffix
#         audio.export(file_name, format=file_suffix[1:])
#         audio_commands.append(command_name)
#         audio_commands.sort()
#         os.remove(message.attachments[0].filename)
#     return

# main function
def main():
    setup_tokens(tokensfile)
    setup_commands()
    pafy.set_api_key(youtube_token)
    client.run(discord_token)

if __name__ == "__main__": main()

