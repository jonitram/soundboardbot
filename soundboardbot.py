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
# maybe change finished from a list to a value/queue
# FINISH COPY - using message -> save('filename') in discord docs

# multiprocessing manager for sharing information across child processes
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
# the video format for videos downloaded from youtube
video_formatting = 'm4a'
# audio commands
audio_commands = []
# other commands sorted in alphabetical order
other_commands = ['cancel','cleanup','clear','create','creating','done','help','list','stop','random','remove','restart','retrim']
# all commands
commands = []

# cleaning up bot messages is set to off by default
cleanup = False

# create preconditions
# max create duration limit in seconds (not necessary, just personal preference)
duration_limit = 30
# video length limit in minutes (currently 45, not necessary, just there to prevent long downloads)
video_length_limit = 45 * 60
# list of commands that are currently being created
creating = None
# list of finished downloaded commands
finished = mpmanager.list()
# maximum number of commands allowed (not necessary, just there to prevent too many files)
audio_command_limit = 100
# reference to the background create command processes (used for cancelling downloads)
create_new_command_process = None
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
            if not filename == creating:
                result.append(filename[len(file_prefix):-len(file_suffix)])
    result.sort()
    return result

# setup the master list of all callable commands
def setup_commands():
    global audio_commands, commands
    audio_commands = build_commands()
    commands = audio_commands + other_commands
    return

def cleanup_files():
    for filename in os.listdir(os.getcwd()):
        if not filename.startswith(file_prefix):
            if filename.endswith(video_formatting) or filename.endswith(file_suffix) or filename.endswith('temp'):
                os.remove(filename)
    return

@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

@client.event
async def on_message(message):
    if message.content.startswith(command_prefix):
        asyncio.create_task(filter_message(message))
        if cleanup:
            asyncio.create_task(delete_message(message))
    return  

async def filter_message(message):
    global audio_task, audio_player
    if audio_task != None and audio_task.done():
            audio_task = None
    command_message = message.content[5:]
    parameters = command_message.split(' ')
    command = parameters[0].lower()
    if command == 'create':
        if len(parameters) != 5:
            error_message = message.author.mention + ' That is not the correct \"create\" command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            # lowercase parameters[2] because that is the command name
            asyncio.create_task(create_command(message, parameters[1], parameters[2].lower(), parameters[3], parameters[4]))
            return
    elif command == 'remove':
        if len(parameters) != 2:
            error_message = message.author.mention + ' That is not the correct \"remove\" command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            # lowercase parameters[1] because that is the command name
            asyncio.create_task(remove_command(message, parameters[1].lower()))
            return
    elif command == 'list':
        asyncio.create_task(send_list_audio_commands(message))
        return
    elif command == 'cleanup':
        asyncio.create_task(cleanup_update(message))
        return
    elif command == 'clear':
        asyncio.create_task(clear(message))
        return
    elif command == 'help':
        asyncio.create_task(send_help(message))
        return
    elif command == 'creating':
        asyncio.create_task(send_creating(message))
        return
    elif command == 'stop':
        await stop_command(message)
        return
    elif command == 'cancel':
        await cancel_creation(message)
        return
    elif command == 'restart':
        await restart_command(message)
        return
    elif command == 'done':
        asyncio.create_task(done_command(message))
        return
    elif command == 'retrim':
        if len(parameters) != 3:
            error_message = message.author.mention + ' That is not the correct \"retrim\" command formatting!'
            asyncio.create_task(check_send_message(message, error_message))
            return
        else:
            asyncio.create_task(retrim_command(message, parameters[1], parameters[2]))
            return
    elif command == creating:
        filename = creating + file_suffix
        if filename in os.listdir(os.getcwd()):
            audio_task = asyncio.create_task(execute_audio_command(message))
            return
        else:
            error_message = message.author.mention + ' This audio command cannot be tested right now: ' + creating
            asyncio.create_task(check_send_message(message, error_message))
    elif command not in commands:
        error_message = message.author.mention + ' That is not a valid command!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif message.author.voice is None:
        error_message = message.author.mention + ' You need to be in a audio channel to use that command!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    else:
        if audio_task == None:
            audio_task = asyncio.create_task(execute_audio_command(message))  
        else:
            error_message = message.author.mention + ' An audio command is currently playing. Please wait for it to finish or use the \"stop\" command before playing a new one.'
            asyncio.create_task(check_send_message(message, error_message))
        return

async def stop_command(message):
    global audio_task, audio_player
    me_as_member = message.channel.guild.me
    if message.author.voice != None:
        if me_as_member.voice != None:
            if message.author.voice.channel == me_as_member.voice.channel:
                if audio_task != None:
                    audio_task.cancel()
                    result = message.author.mention + ' The currently playing audio command has stopped.'
                    await audio_player.disconnect()
                    audio_player = None
                    audio_task = None
                else:
                    print('***Concurrency Error, should not be possible***')
            else:
                result = message.author.mention + ' You have to be in the same voice channel as the bot to use the \"stop\" command.'
        else:
            result = message.author.mention + ' There is no audio command currently playing.'
    else:
        result = message.author.mention + ' You have to be in a voice channel to use the \"stop\" command.'
    asyncio.create_task(check_send_message(message, result))
    return

async def clear(message):
    deleted = 0
    me_as_member = message.channel.guild.me
    if not message.channel.permissions_for(me_as_member).manage_messages:
        error_message = message.author.mention + ' ' + client.user.mention + ' does not have permission to remove messages! '
        asyncio.create_task(check_send_message(message, error_message))
        return
    else:
        deleted = asyncio.create_task(message.channel.purge(limit=500, check=clear_conditions))
        while True:
            try:
                deleted.result()
            except asyncio.base_futures.InvalidStateError:
                await asyncio.sleep(1)
            else:
                break
        asyncio.create_task(message.channel.send('Deleted {} message(s).'.format(len(deleted.result()))))
    return

def clear_conditions(message):
    current_message = message.content
    return message.author == client.user or current_message.startswith(command_prefix)

async def cleanup_update(message):
    global cleanup
    cleanup = not cleanup
    if cleanup:
       cleanup_update_message = message.author.mention + ' any messages beginning with the \"' +command_prefix + '\" command prefix will now be deleted.'
       asyncio.create_task(check_send_message(message, cleanup_update_message))
    else:
       cleanup_update_message = message.author.mention + ' Commands issued to the bot will no longer be deleted.'
       asyncio.create_task(check_send_message(message, cleanup_update_message))
    return

async def remove_command(message, audio_command):
    if audio_command == creating:
        await cancel_creation(message)
        return
    elif audio_command not in audio_commands:
        error_message = message.author.mention + ' That audio command does not exist!'
        asyncio.create_task(check_send_message(message, error_message))
        return
    elif remove_audio_file(audio_command):
        update = message.author.mention + ' The \"' + audio_command + '\" audio command has been removed.'
    else:
        update = message.author.mention + ' The requested audio command\'s file could not be found! The ' + audio_command + ' audio command has been removed.'
    setup_commands()
    asyncio.create_task(check_send_message(message, update))
    return
        
def remove_audio_file(audio_command):
    file_name = file_prefix + audio_command + file_suffix
    if file_name in os.listdir(os.getcwd()):
        os.remove(file_name)
        return True
    return False

async def send_creating(message):
    list_creating_message = message.author.mention + ' ' + list_creating()
    asyncio.create_task(check_send_message(message, list_creating_message))
    return

def list_creating():
    result = 'Here is a list of all currently audio commands currently being created: '
    if creating != None:
        result += creating
    else:
        result += 'No commands are currently being created!'
    return result

async def send_list_audio_commands(message):
    list_audio_message = message.author.mention + ' ' + list_audio_commands()
    asyncio.create_task(check_send_message(message, list_audio_message))
    return

def list_audio_commands():
    result = 'Here is a list of all audio commands: '
    if len(audio_commands) > 0:
        for command in audio_commands:
            result += command + ', '
        result += ' and random.\n'
        result += 'The \"random\" audio command will randomly play an existing audio command.'
    else:
        result += 'There are no audio commands yet!'
    return result

async def execute_audio_command(message):
    global audio_player
    audio_channel = message.author.voice.channel
    me_as_member = message.channel.guild.me
    if audio_channel.permissions_for(me_as_member).speak:
        command = message.content[5:]
        file = get_sound(command)
        if command == creating:
            file = creating + file_suffix
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
    error_message = message.author.mention + ' ' + client.user.mention + ' cannot speak in your audio channel!'
    asyncio.create_task(check_send_message(message, error_message))
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
    help_message = message.author.mention + ' Issue a command by typing \"' + command_prefix + '\" followed by a space and then the command to execute it.\n'
    help_message += '- ' + list_audio_commands() + '\n'
    help_message += 'You must be in an audio channel to use an audio command.\n'
    help_message += '- \"stop\" : Stops a currently playing audio command.\n'
    help_message += '- \"create <YouTubeURL> <CommandName> <StartTime(Min:Sec)> <Duration(Sec)>\" : Creates an audio command called <CommandName>.\n' 
    help_message += 'Each parameter of the \"create\" command must be separated by exactly a single space. Only one audio command can be created at a time.\n'
    help_message += 'You will get a chance to test your command before saving it.\n'
    help_message += '- \"retrim <StartTime(Min:Sec)> <Duration(Sec)>\" : Retrims the audio command currently being created before it is saved.\n'
    help_message += '- \"done\" : Completes the \"create\" command process and saves your command.\n'
    help_message += '- \"creating\" : Lists the audio command currently being created.\n'
    help_message += '- \"cancel\" : Cancels the currently audio comamnd currently being created.\n'
    # help_message += 'Turn your own sound file into a command using the \"copy\" command followed by a space and \" <CommandName>\" along with uploading a single sound file attached to the message.'
    # help_message += 'Uploaded sound files can be no longer than ' + duration_limit + ' seconds.\n'
    help_message += '- \"remove <CommandName>\" : Removes the <CommandName> audio command.\n'
    help_message += '- \"list\" : Lists all audio commands available.\n'
    help_message += '- \"cleanup\" : Toggles automatically deleting commands issued to the bot.\n'
    help_message += 'Currently: '
    if cleanup:
        help_message += 'Enabled'
    else:
        help_message += 'Disabled'
    help_message += '.\n'
    help_message += '- \"clear\" : Deletes commands issued to the bot and messages sent by the bot (up to 500 messages back).\n'
    help_message += '- \"restart\" : Stops all audio commands, cancels all downloads, and restarts the bot.\n'
    help_message += 'This command will only work if the bot is still responding to messages.\n'
    help_message += '- \"help\" : Sends this message.'
    asyncio.create_task(check_send_message(message, help_message))
    return

async def delete_message(message):
    me_as_member = message.channel.guild.me
    if message.channel.permissions_for(me_as_member).manage_messages:
        asyncio.create_task(message.delete())
    else:
        error_message = message.author.mention + ' ' + client.user.mention + ' does not have permission to remove messages!'
        asyncio.create_task(check_send_message(message, error_message))
    return

def check_create_preconditions(url, command_name, start_time, duration):
    result = None
    try:
        video = pafy.new(url)
    except ValueError:
        result = 'Please enter a YouTube URL for the \"create\" command.'
    else:
        if not check_duration_formatting(duration):
            result = 'That is not the correct \"Duration\" formatting!'
        else:
            if not check_start_time_formatting(start_time):
                result = 'That is not the correct starting time format! Please use <Minutes>:<Seconds>!'
            else:
                min_and_seconds = start_time.split(':')
                start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
                if command_name in commands:
                    result = 'That command is already defined! If it is a audio command, please delete that audio command first!'
                elif video.length > video_length_limit:
                    result = 'That video would take too long to download, find a shorter video (' + video_length_limit + ' min or less).'
                elif command_name == creating:
                    result = 'That command is currently being created. Please label your command something else.'
                elif len(audio_commands) > audio_command_limit:
                    result = 'There are already ' + str(audio_command_limit) + ' audio commands! Please remove an audio command before adding a new one.'
                elif float(duration) <= 0:
                    result = 'Duration must be greater than 0!'
                elif float(duration) > duration_limit:
                    result = 'Duration is far too long! Nobody wants to listen to your command drone on forever.'
                elif start_time_seconds <= 0:
                    result = 'The starting time must be greater than 0:00! (You can use decimals to get around this i.e. 0:00.1)'
                elif start_time_seconds >= video.length:
                    result = 'The starting time must be within the video\'s length!'
                # add 1 because pafy only returns seconds rounded down for precondition comparison, this is for any milliseconds pafy wouldn't account for
                elif start_time_seconds + float(duration) > (1 + video.length):
                    result = 'You cannot have the duration extend passed the end of the video!'
                elif creating != None:
                    result = 'Too many commands being created at once! Please wait for another command to finish before creating a new one!'
                else:
                    # create command is good to go, just going to update the creator on video length duration
                    result = 'The currently downloading video is this long: ' + str(video.duration) + '.'
    return result

def check_start_time_formatting(start_time):
    min_and_seconds = start_time.split(':')
    if len(min_and_seconds) != 2:
        return False
    try:
        float(min_and_seconds[0])
    except ValueError:
        return False
    else:
        try:
            float(min_and_seconds[1])
        except ValueError:
            return False
        else:
            return True

def check_duration_formatting(duration):
    try:
        float(duration)
    except ValueError:
        return False
    else:
        return True

async def create_command(message, url, command_name, start_time, duration):
    global creating, create_new_command_process
    create_preconditions = check_create_preconditions(url, command_name, start_time, duration)
    if not create_preconditions.startswith("The currently downloading video is this long:"):
        error_message = message.author.mention + ' ' + create_preconditions
        asyncio.create_task(check_send_message(message, error_message))
        return
    creating = command_name
    create_new_command_process = multiprocessing.Process(target=create_new_command, args=(url, command_name, start_time, duration))
    create_new_command_process.start()
    update = message.author.mention + ' Beginning to create the \"' + command_name + '\" audio command!'
    asyncio.create_task(check_send_message(message, update))
    asyncio.create_task(check_send_message(message, create_preconditions))
    asyncio.create_task(finished_command(message))
    return

async def done_command(message):
    global creating, create_new_command_process
    if creating != None:
        result = message.author.mention + ' A new audio command can now be created.'
        result += 'This command has been saved: ' + creating
        current_file_name = creating + file_suffix
        command_file_name = file_prefix + creating + file_suffix
        os.rename(src=current_file_name,dst=command_file_name)
        setup_commands()
        multiprocessing.Process(target=cleanup_files).start()
        create_new_command_process = None
        creating = None
    else:
        result = message.author.mention + ' Nothing is being created at this time.'
    asyncio.create_task(check_send_message(message, result))
    return

async def finished_command(message):
    global finished, creating, create_new_command_process
    while len(finished) == 0:
        await asyncio.sleep(1)
    command = finished[0]
    finished.remove(command)
    filename = creating + file_suffix
    if filename in os.listdir(os.getcwd()):
        result = 'This audio command has finished downloading: ' + command + '\n'
        result += 'You can now test the audio command. If you would like to retrim the audio, use the \"retrim <StartTime(Min:Sec)> <Duration(Sec)>\" command.'
        result += 'If you are satisfied with the audio command, use the \"done\" command to complete creating the command.'
    else:
        result = message.author.mention + ' Something went wrong when creating this command: '
        result += command + '\n'
        video_file_name = command + '.' + video_formatting
        if video_file_name in os.listdir(os.getcwd()):
            result += 'Your command duration extended < 1 second passed the end of the video. Please use the \"retrim <StartTime(Min:Sec)> <Duration(Sec)>\" command to fix your command.'
        else:
            result += 'The video cannot be downloaded.'
            multiprocessing.Process(target=cleanup_files).start()
            creating = None
    asyncio.create_task(check_send_message(message, result))
    return

def create_new_command(url, command_name, start_time, duration):
    global finished
    video = pafy.new(url)
    download_video_process = multiprocessing.Process(target=download_video, args=(command_name, video, video_formatting), daemon=True)
    download_video_process.start()
    download_video_process.join()
    min_and_seconds = start_time.split(':')
    start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
    trim_and_create_process = multiprocessing.Process(target=trim_and_create, args=(video_formatting, command_name, start_time_seconds, duration), daemon=True)
    trim_and_create_process.start()
    trim_and_create_process.join()
    finished.append(command_name)
    return

def download_video(command_name, video, video_formatting):
    best_audio = video.getbestaudio(preftype=video_formatting)
    file_name = command_name + '.' + video_formatting
    try:
        best_audio.download(filepath=file_name,quiet=True,remux_audio=True)
    except FileNotFoundError:
        print('This video failed to download: ' + video.title)
    return

def retrim_command_preconditions(start_time, duration):
    result = None
    if creating == None:
        result = 'Nothing is being created at this time.'
    elif not check_duration_formatting(duration):
            result = 'That is not the correct \"Duration\" formatting!'
    else:
        if not check_start_time_formatting(start_time):
            result = 'That is not the correct starting time format! Please use <Minutes>:<Seconds>!'
        else:
            min_and_seconds = start_time.split(':')
            start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
            if float(duration) <= 0:
                result = 'Duration must be greater than 0!'
            elif float(duration) > duration_limit:
                result = 'Duration is far too long! Nobody wants to listen to your command drone on forever.'
                result += 'Please make your command shorter than : ' + duration_limit + ' seconds.'
            elif start_time_seconds <= 0:
                result = 'The starting time must be greater than 0:00! (You can use decimals to get around this i.e. 0:00.1)'
    return result

async def retrim_command(message, start_time, duration):
    update = message.author.mention + ' '
    error = retrim_command_preconditions(start_time, duration)
    if error == None:
        min_and_seconds = start_time.split(':')
        start_time_seconds = (float(min_and_seconds[0]) * 60) + float(min_and_seconds[1])
        trim_and_create(video_formatting, creating, start_time_seconds, duration)
        filename = creating + file_suffix
        if filename in os.listdir(os.getcwd()):
            update += 'This audio command has finished retrimming: ' + creating
        else:
            update += 'Your command duration extended < 1 second passed the end of the video. Please use the \"retrim <StartTime(Min:Sec)> <Duration(Sec)>\" command to fix your command.'
    else:
        update += error
    asyncio.create_task(check_send_message(message, update))
    return

def trim_and_create(video_formatting, command_name, start_time_seconds, duration_seconds):
    file_name = command_name + file_suffix
    if file_name in os.listdir(os.getcwd()):
        os.remove(file_name)
    formatting = file_suffix[1:]
    video_file = command_name + '.' + video_formatting
    video_audio = AudioSegment.from_file(video_file,video_formatting)
    audio_length = video_audio.duration_seconds
    start_time_ms = (audio_length - start_time_seconds) * -1000
    duration_ms = float(duration_seconds) * 1000
    # check to make sure milliseconds are within video duration length
    if float(start_time_seconds) + float(duration_seconds) <= audio_length:
        starting_audio = video_audio[start_time_ms:]
        final_audio = starting_audio[:duration_ms]
        final_audio.export(file_name, format=formatting)
    return

async def check_send_message(message, message_content):
    me_as_member = message.channel.guild.me
    if message.channel.permissions_for(me_as_member).send_messages:
        await message.channel.send(message_content)
    return

async def cancel_creation(message):
    global create_new_command_process, finished, creating
    if creating != None:
        if create_new_command_process.is_alive():
            create_new_command_process.kill()
        create_new_command_process = None
        if creating in finished:
            finished.remove(creating)
        multiprocessing.Process(target=cleanup_files).start()
        update = message.author.mention + ' The audio command \"' + creating + '\" currently being created has been stopped.'
        creating = None
    else:
        update = message.author.mention + ' Nothing is being created at this time.'
    await check_send_message(message, update)
    return

async def restart_command(message):
    update = message.author.mention + ' Restarting the bot.'
    if audio_task != None:
        await stop_command(message)
    if creating != None:
        await cancel_creation(message)
    await check_send_message(message, update)
    os.execv(sys.executable, ['python3.7'] + sys.argv)
    return

# copy command logic
# command_prefix copy <command_name>'
# so len(parameters) == 2 in filter_message
# only one attachment allowed
# so len(message.attachments) == 1
# check filetype for audio file
# check for existence of command
# check audio_command_limit
# download audio
# check audio duration, if >= duration_limit -> too long
# filename = file_prefix + command_name (parameters[1]) + file_suffix
# export file following create command

# main function
def main():
    multiprocessing.Process(target=cleanup_files).start()
    setup_tokens(tokensfile)
    setup_commands()
    pafy.set_api_key(youtube_token)
    client.run(discord_token)

if __name__ == "__main__": main()
