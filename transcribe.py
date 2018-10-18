from speechTranscriber import SpeechTranscriber

if __name__ == '__main__':
    speechTranscriber = SpeechTranscriber()

    while True:
        var = input("Enter command (pause/start/shutdown) or text: \n")
        if (str(var)=="pause"):
            speechTranscriber.pauseRecording() 
        elif (str(var)=="start"):
            speechTranscriber.startRecording()
        elif (str(var)=="shutdown"):
            speechTranscriber.shutDown()
            break
        else:
            if (str(var) is not ""):
                speechTranscriber.sendOsc(str(var)) 