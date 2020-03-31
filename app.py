import argparse
import os, sys
from threading import Thread
import logging
import asyncio
import vlc, pafy
from PyQt5 import QtCore, QtWidgets, QtGui, uic

from bot import *

class SongRequest():
    
    def __init__(self, url):
        self.Video = pafy.new(url).getbest()
        self.Media = vlc.Media(self.Video.url)
        #self.Media.set_meta(vlc.Meta.NowPlaying, self.Video.title)
        #self.Media.save_meta()


class MediaPlayer():
    
    vlc_instance = vlc.Instance() # --playlist-enqueue ???
    media_player = vlc_instance.media_player_new()
    media_list_player = vlc_instance.media_list_player_new()
    media_list = vlc_instance.media_list_new()

    def __init__(self, hwnd, volume, bot):

        def media_end_cb(event, media_list, media_list_player):
            media_list.remove_index(0)
            media_list_player.previous()

        def media_list_player_played_cb(event, media_list_player):
            bot.skip_requests.clear()
        
        self.media_player.set_hwnd(hwnd)
        self.media_list_player.set_media_player(self.media_player)
        self.media_list_player.set_media_list(self.media_list)
        self.media_player.stop()
        self.media_player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, 
                                          media_end_cb, 
                                          media_list=self.media_list, 
                                          media_list_player=self.media_list_player)
        
        self.media_player.event_manager().event_attach(vlc.EventType.MediaPlayerMediaChanged, 
                                          media_list_player_played_cb,
                                          media_list_player=self.media_list_player)

        self.media_player.audio_set_volume(volume)
        




class MainWindow(QtWidgets.QMainWindow):

       
    # event stuff
    loop = asyncio.new_event_loop()

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()
        self.ui = uic.loadUi('MainWindow.ui', self)
        
        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('--release')
        args = arg_parser.parse_args()
        logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO if args.release == "1" else logging.DEBUG)


        # Bot Background Thread
        self.bot = Bot(self, args)
        self.bot_thread = BotThread(self.bot)
        self.bot_thread.start()


        # Song Request VLC Player
        self.media_player = MediaPlayer(int(self.ui.mediaFrame.winId()), 10, self.bot)
        #self.media_player.setName("media_player")
        self.is_playing = 0

        # TTS VLC Player
        self.tts_player = MediaPlayer(int(self.ui.ttsFrame.winId()), 80, self.bot)
        #self.tts_player.setName("tts_player")
        self.tts_enabled = True

        # UI Buttons
        self.ui.playPause.pressed.connect(self.onPlayPressed)
        self.ui.stopButton.pressed.connect(self.onStopPressed)
        self.ui.skipButton.pressed.connect(self.onSkipPressed)
        self.ui.volumeSlider.valueChanged.connect(self.onMediaVolumeChanged)

        self.ui.ttsEnableButton.pressed.connect(self.onTTSEnablePressed)
        self.ui.ttsSkipButton.pressed.connect(self.onTTSSkipPressed)
        self.ui.ttsVolumeSlider.valueChanged.connect(self.onTTSVolumeChanged)

    def onMediaVolumeChanged(self):
        self.media_player.media_player.audio_set_volume(int(self.ui.volumeSlider.value()))
        self.ui.volumeNumber.setText(str(self.ui.volumeSlider.value()))
                  
    def onTTSVolumeChanged(self):
        self.tts_player.media_player.audio_set_volume(int(self.ui.ttsVolumeSlider.value()))
        self.ui.ttsVolumeNumber.setText(str(self.ui.ttsVolumeSlider.value()))

    def onPlayPressed(self):
        if (self.is_playing == 1): #pause
            self.ui.playPause.setText('Play')
            self.media_player.media_list_player.pause()
            self.is_playing = 0

        else:
            self.ui.playPause.setText('Pause') #play
            self.media_player.media_list_player.play()
            self.is_playing = 1


    def onStopPressed(self):
        self.ui.playPause.setText('Play')
        self.media_player.media_list_player.stop()
        self.is_playing = 0
        

    def onSkipPressed(self):
        self.media_player.media_list_player.stop()
        self.media_player.media_list.remove_index(0)
        self.media_player.media_list_player.play()

        
    def onTTSEnablePressed(self):
        if (self.tts_enabled == True):
            self.ui.ttsEnableButton.setText('Enable')
            self.tts_player.media_list_player.pause()
            self.tts_enabled = False
        else:
            self.ui.ttsEnableButton.setText('Disable')
            self.tts_player.media_list_player.play()
            self.tts_enabled = True

    def onTTSSkipPressed(self):
        self.tts_player.media_list_player.stop()
        self.tts_player.media_list.remove_index(0)
        self.tts_player.media_list_player.play()
        


    async def AddMedia(self, uri):
        song = SongRequest(uri)

        self.media_player.media_list.add_media(song.Media)
        if (self.is_playing == 1):
            self.media_player.media_list_player.play()
        return song

    def AddTTSMessage(self, text):
        API = "https://us-central1-sunlit-context-217400.cloudfunctions.net/streamlabs-tts"
        PARAMS = {'text': text, 'voice':'Brian'}
        response = requests.post(url = API, data = PARAMS).json()
        logging.debug(response)
        if (response['success'] == True):
            audioUrl = response['speak_url']
            self.tts_player.media_list.add_media(vlc.Media(audioUrl))
            if (self.tts_enabled == True):
                self.tts_player.media_list_player.play()

        else:
            logging.critical("Error in TTS Message, you may be rate limited")




               
if __name__ == "__main__":

    load_dotenv()
    tracemalloc.start()

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
    

