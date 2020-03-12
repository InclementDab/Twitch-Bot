import argparse
import os, sys, threading
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

        

class MainWindow(QtWidgets.QMainWindow):


    # media player stuff
    vlc_instance = vlc.Instance() # --playlist-enqueue ???

    # song request
    media_player = vlc_instance.media_player_new()
    media_list_player = vlc_instance.media_list_player_new()
    media_list = vlc_instance.media_list_new()

    # tts request
    tts_media_player = vlc_instance.media_player_new()
    tts_media_list_player = vlc_instance.media_list_player_new()
    tts_media_list = vlc_instance.media_list_new()

    
    # event stuff
    loop = asyncio.new_event_loop()

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()
        self.ui = uic.loadUi('MainWindow.ui', self)
        
        parser = argparse.ArgumentParser()
        parser.add_argument('--release')
        args = parser.parse_args()
        logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO if args.release == "1" else logging.DEBUG)


        def media_end_callback(event, media_list, media_list_player):
            logging.debug("media_end_callback")
            media_list.remove_index(0)
            media_list_player.previous()
            

        # Song Request VLC Player
        self.media_player.set_hwnd(int(self.ui.mediaFrame.winId()))
        self.media_list_player.set_media_player(self.media_player)
        self.media_list_player.set_media_list(self.media_list)
        self.media_player.stop()
        self.is_playing = 0
        self.media_player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, 
                                          media_end_callback, 
                                          media_list=self.media_list, 
                                          media_list_player=self.media_list_player)
        
        # TTS VLC Player
        self.tts_media_player.set_hwnd(int(self.ui.ttsFrame.winId()))
        self.tts_media_list_player.set_media_player(self.tts_media_player)
        self.tts_media_list_player.set_media_list(self.tts_media_list)
        self.tts_media_player.stop()
        self.tts_enabled = True
        self.tts_media_player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, 
                                              media_end_callback, 
                                              media_list=self.tts_media_list, 
                                              media_list_player=self.tts_media_list_player)

        # Bot Background Thread
        self.bot = Bot(self, args)
        self.bot_thread = BotThread(self.bot)
        self.bot_thread.start()

        # UI Buttons
        self.ui.playPause.pressed.connect(self.onPlayPressed)
        self.ui.stopButton.pressed.connect(self.onStopPressed)
        self.ui.skipButton.pressed.connect(self.onSkipPressed)
        self.ui.doStartBot.pressed.connect(self.onTest)
        self.ui.volumeSlider.valueChanged.connect(self.VolumeChanged)

        self.ui.ttsEnableButton.pressed.connect(self.onTTSEnablePressed)
        self.ui.ttsSkipButton.pressed.connect(self.onTTSSkipPressed)
                  
            
       

    def onPlayPressed(self):
        if (self.is_playing == 1): #pause
            self.ui.playPause.setText('Play')
            self.media_list_player.pause()
            self.is_playing = 0

        else:
            self.ui.playPause.setText('Pause') #play
            self.media_list_player.play()
            self.is_playing = 1


    def onStopPressed(self):
        self.ui.playPause.setText('Play')
        self.media_list_player.stop()
        self.is_playing = 0
        

    def onSkipPressed(self):
        self.media_list_player.stop()
        self.media_list.remove_index(0)
        self.media_list_player.play()
        
    def onTTSEnablePressed(self):
        if (self.tts_enabled == True):
            self.ui.ttsEnableButton.setText('Enable')
            self.tts_media_list_player.pause()
            self.tts_enabled = False
        else:
            self.ui.ttsEnableButton.setText('Disable')
            self.tts_media_list_player.play()
            self.tts_enabled = True

    def onTTSSkipPressed(self):
        self.tts_media_list_player.stop()
        self.tts_media_list.remove_index(0)
        self.tts_media_list_player.play()
        


    async def AddMedia(self, uri):
        song = SongRequest(uri)

        self.media_list.add_media(song.Media)
        if (self.is_playing == 1):
            self.media_list_player.play()
        return song

    def AddTTSMessage(self, text):
        API = "https://us-central1-sunlit-context-217400.cloudfunctions.net/streamlabs-tts"
        PARAMS = {'text': text, 'voice':'Brian'}
        response = requests.post(url = API, data = PARAMS).json()
        logging.debug(response)
        if (response['success'] == True):
            audioUrl = response['speak_url']
            self.tts_media_list.add_media(vlc.Media(audioUrl))
            if (self.tts_enabled == True):
                self.tts_media_list_player.play()

        else:
            logging.critical("Error in TTS Message, you may be rate limited")

    def onTest(self):
        #self.AddTTSMessage(text="juliet")    
        #self.AddTTSMessage(text="brian")    
        #self.AddTTSMessage(text="richard")    
        self.tts_media_list.add_media(vlc.Media("https://polly.streamlabs.com/v1/speech?OutputFormat=ogg_vorbis&Text=juliet&VoiceId=Brian&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAIHKNQTJ7BGLEFVZA%2F20200312%2Fus-west-2%2Fpolly%2Faws4_request&X-Amz-Date=20200312T180929Z&X-Amz-SignedHeaders=host&X-Amz-Expires=900&X-Amz-Signature=37e13c61666959953b347ee48cf926908b0d15127a0fc8fc4ffd8ea1f04b57e9"))
        self.tts_media_list.add_media(vlc.Media("https://polly.streamlabs.com/v1/speech?OutputFormat=ogg_vorbis&Text=brian&VoiceId=Brian&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAIHKNQTJ7BGLEFVZA%2F20200312%2Fus-west-2%2Fpolly%2Faws4_request&X-Amz-Date=20200312T180930Z&X-Amz-SignedHeaders=host&X-Amz-Expires=900&X-Amz-Signature=188d3c25141f3b2046777739cbb8915fbccb6e40ebc515db2df79f2b617941f1"))
        self.tts_media_list.add_media(vlc.Media("https://polly.streamlabs.com/v1/speech?OutputFormat=ogg_vorbis&Text=richard&VoiceId=Brian&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAIHKNQTJ7BGLEFVZA%2F20200312%2Fus-west-2%2Fpolly%2Faws4_request&X-Amz-Date=20200312T180930Z&X-Amz-SignedHeaders=host&X-Amz-Expires=900&X-Amz-Signature=fa52503ee9c661338f8a65cf2aca067c08da79b3f8442ade42aa8eee5227ab0b"))
        self.tts_media_list_player.play()
        #self.ui.videoTitle.setText(self.media_player.get_media().get_meta(vlc.Meta.NowPlaying))

    def VolumeChanged(self):
        value = self.ui.volumeSlider.value()
        self.media_player.audio_set_volume(value)



               
if __name__ == "__main__":

    load_dotenv()
    tracemalloc.start()

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
    

