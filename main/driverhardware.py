import serial
import time
import threading
import struct
import math

from .dataman import dataman


class PID:

    def __init__(self,setpoint=0,kp=1,ki=0,kd=0,ts=1):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.ts = ts
        self.error = 0
        self.output = 0
        self.integralsat = 50

    def reset(self):
        self.error = 0
        self.output = 0
        self.integral = 0

    def update(self,reading):        
        self.lasterror = self.error
        self.error = self.setpoint - reading
        self.integral = self.integral + (self.error*self.ts)
        if abs(self.integral) > self.integralsat:
            self.integral = math.copysign(self.integralsat,self.integral)
        self.derivada = (self.error - self.lasterror) / self.ts
        self.output = self.kp * self.error + self.ki * self.integral + self.kd * self.derivada
        if self.output > 100.0:
            self.output = 100
        elif self.output < 0:
            self.output = 0
        return self.output


class driverhardware():

    def __init__(self):   
        super(). __init__()
        self.Tsample = 1.0
        self.serial = serial.Serial(port=None,
                                    baudrate = 19200,
                                    parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE,
                                    bytesize=serial.EIGHTBITS,
                                    timeout=400)
        if self.serial.isOpen():
            self.serial.close()

        self.flagstop = False
        self.flagrunning = False
        self.starttime = None
        self.flagstart = False

        # Enable map: quais termopares e entradas devem ser lidas
        self.enablemap = [False,False,False,False,False,False,False,False,False,False]
        # Variáveis de controle:
        self.tipoctrl = "off"
        self.termoparctrl = 0
        self.manuallevel = 0.0

        self.MAX_TIME = 60 * 24 # 24 horas em minutos
        self.dman = dataman(self.MAX_TIME)

        self.dummymode = False
        self.dummytable = [b"\x06\x4F\x00",b"\x01\x90\x00",b"\x00\x01\x00",
                  b"\xFF\xFC\x00",b"\xFF\xF0\x00",b"\xF0\x60\x00",
                  b"\xF0\x60\x00",b"\x01\x90\x00"]  
        self.dummyjunta = b"\xE7\x00"

        self.pid = PID()

        self.statusdict = {"state":"stopped","status":"nodata","data":{}}

        
    def openSerial(self):
        self.serial.open()


    def handshake(self):
        self.serial.reset_output_buffer()
        self.serial.reset_input_buffer()
        # Tenta fazer o handshake 2 vezes:
        for k in range(2):
            self.serial.write(b'h')
            if self.serial.read(1) == b'k':
                return True
            self.serial.reset_output_buffer()
            self.serial.reset_input_buffer()
            time.sleep(0.1)
            # QThread.msleep(100)
        raise Exception("Handshake com dispositivo falhou.")


    def writeThermType(self,tipo):
        cmd = f's{tipo}'[0:2].encode() # Comando para setar tipo de termopar.
        self.serial.write(cmd)
        time.sleep(0.05)
        aux = self.serial.read(2)
        if aux.decode() != f'k{tipo}':
            print("Falhou!") # TODO: Raise exception!

    
    def writeManualCtrlLevel(self,level=None):
        if self.dummymode: 
            return
        if level is None: 
            convertedlevel = int(round(self.manuallevel))
        else:
            convertedlevel = int(round(level))
        cmd = [ord('m'), convertedlevel]
        self.serial.write(cmd)
        # TODO: get response from system to confirm.


    # def writeCtrlKs(self):
    #     if self.dummymode: 
    #         return
    #     self.serial.write(ord('j'))
    #     self.serial.write(struct.pack("<fff", self.ks[0], self.ks[1], self.ks[2])) # Kp, Ki, Kd
    #     # TODO: Ler confirmação.
    #     ''' 
    #         No lado do Arduino:
    #             Serial.readBytes((char *) &kp, sizeof(float));
    #             Serial.readBytes((char *) &ki, sizeof(float));
    #             Serial.readBytes((char *) &kd, sizeof(float));
    #         one kp, ki e kd devem ser variáveis definidas como floats: float kp, ki, kd.
    #         Fonte: https://stackoverflow.com/questions/59505221/sending-floats-as-bytes-over-serial-from-python-program-to-arduino
    #     '''


    def ctrlOff(self):
        if self.dummymode: 
            return
        # cmd = [ord('m'), 255]
        cmd = [ord('m'), 0]
        self.serial.write(cmd)
        # TODO: get response from system. 


    def iniciaLeituras(self,amostragem,enablemap,tipotermopar,porta):
        if not self.flagrunning:
            self.serial.port = porta
            self.Tsample = float(amostragem) # TODO: What to do if user changes sampling rate without resetting data?
            # mytimer.setTimerInterval(amostragem * 1000)
            self.tipotermopar = tipotermopar            
            self.enablemap = enablemap
            self.flagstart = True
            self.trd = threading.Thread(target=self.realizaLeituras)
            self.trd.start()

    def limpaLeituras(self):
        self.starttime = None
        self.statusdict = {"status":"nodata","data":{}}
        self.dman.resetData(self.Tsample)


    def paraLeituras(self):
        if self.flagrunning:
            self.flagstop = True            


    def changeSetPoint(self,value):
        self.pid.setpoint = value


    def changeManualCtrlLevel(self,value):
        self.manuallevel = float(value)


    def changeCtrlType(self,tipo):
        self.tipoctrl = tipo


    def setCtrlConfig(self,tipo,termopar,kp,ki,kd):
        # print(tipo)
        self.tipoctrl = tipo
        self.termoparctrl = termopar
        self.pid.kp = kp
        self.pid.kd = kd
        self.pid.ki = ki


    def leTermopar(self,idx):
        if self.dummymode:
            time.sleep(0.15)
            # QThread.msleep(150)
            resp = self.dummytable[idx] + self.dummyjunta
        else:
            cmd = f'r{idx}'.encode() # Comando para leitura: uma string com r seguido do número (como string)
            self.serial.write(cmd)
            time.sleep(0.15)
            # QThread.msleep(150)
            resp = self.serial.read(5)  # Resposta sempre em 5 bytes: os 3 primeiros correspondem à leitura, os outros 2 à junta fria.

        if resp[0] == 0x80:
            if resp[2] == 0x00:
                text = "Open"
            elif resp[2] == 0x01:
                text = "Over"
            elif resp[2] == 0x02:
                text = "IOOR"
            elif resp[2] == 0x03:
                text = "EOOR"
            val = float("nan")
            juntafria = None
        else:           
            aux = int.from_bytes(resp[0:3],byteorder='big',signed=True)
            val = round(float(aux) / (2**12),2)
            aux = int.from_bytes(resp[3:5],byteorder='big',signed=True) 
            juntafria = round(float(aux) / (2**8),2)            
            text = f"{val:.2f}"
        return val,juntafria,text


    def leADC(self,idx):
        if self.dummymode:
            time.sleep(0.15)
            val = 10.0
            text = "10"
        else:
            cmd = f'a{idx}'.encode() # Comando para leitura: uma string com r seguido do número (como string)
            self.serial.write(cmd)
            time.sleep(0.05)
            # QThread.msleep(150)
            resp = self.serial.read(2)  # Resposta sempre em 5 bytes: os 3 primeiros correspondem à leitura, os outros 2 à junta fria.
            val = float(int.from_bytes(resp[0:2],byteorder='big',signed=False))                       
            text = f"{val:.0f}"
        return val,text


    def sampletimeout(self):
        # if (self.flagrunning):
        #     self.flagsampletimeout = True
        # print(time.time())
        # condwait.wakeAll()
        # print(time.time())
        pass


    def realizaLeituras(self):

        mydict = {}

        while True: 

            temptime = time.time()                    

            if self.flagstart:
                if not self.flagrunning:
                    try:
                        if not self.dummymode:
                            self.openSerial()
                            time.sleep(1.5)  # TODO: Check if this time can be reduced.
                            # QThread.msleep(1500)
                            self.handshake()
                            time.sleep(0.1)
                            # QThread.msleep(100)
                            self.writeThermType(self.tipotermopar)
                        self.flagrunning = True                        
                        self.pid.reset()
                        if self.starttime is None:
                            self.dman.resetData(int(self.Tsample))
                            self.starttime = round(time.time(),2)
                        # self.realizaLeituras()                
                        self.flagstop = False
                        self.flagrunning = True    
                        self.statusdict["state"] = "running"                    
                    except Exception as e:
                        self.flagrunning = False
                        if self.serial.isOpen():
                            self.serial.close()
                        # TODO: self.mwindow.errorStarting(str(e))
                        self.statusdict["state"] = "stopped"
                        self.statusdict["status"] = "error"
                        self.statusdict["emessage"] = str(e)
                        print(str(e))
                        return
                self.flagstart = False

            if not self.flagrunning:
                
                # QThread.sleep(1)
                time.sleep(1)

            else:

                if self.flagstop:  

                    self.ctrlOff()        
                    if self.serial.isOpen():                
                        self.serial.close()
                    self.flagrunning = False
                    self.flagstop = False
                    rtimeaux = round(time.time() - self.starttime,2)
                    for k in range(8):
                        self.dman.appendTData(k, rtimeaux, float("nan"))
                        # appendEmptyData(k,rtimeaux)
                    self.dman.incrementCtReadings()
                    self.statusdict["state"] = "stopped"
                    self.statusdict["status"] = "nodata"  
                    return

                else:

                    axxx = time.time()

                    readtime = int(time.time()) - self.starttime
                    # self.mwindow.setCurTime(readtime)
                    mydict['readtime'] = round(readtime)

                    autotermopread = -1
                    junta = 0
                    
                    if (self.tipoctrl == 'off'):
                        self.ctrlOff()
                        self.dman.setpoint = None
                        # self.mwindow.setPowerText(f"0%")
                        mydict["power"] = f"0"
                    elif (self.tipoctrl == 'manual'):
                        self.writeManualCtrlLevel()
                        self.dman.setpoint = None
                        # self.mwindow.setPowerText(f"{self.manuallevel:.0f}%")
                        mydict["power"] = f"{self.manuallevel:.0f}"
                    elif (self.tipoctrl == 'auto'):
                        self.dman.setpoint = self.pid.setpoint
                        val,juntaaux,text = self.leTermopar(self.termoparctrl)
                        if not math.isnan(val):
                            self.pid.update(val)
                            # self.mwindow.setPowerText(f"{self.pid.output:.0f}%")                            
                            mydict["power"] = f"{self.pid.output:.0f}"
                            self.writeManualCtrlLevel(level=self.pid.output)
                        else: 
                            self.writeManualCtrlLevel(level=0)
                            mydict["power"] = "0"
                        rtimeaux = round((time.time()) - self.starttime,2)
                        if juntaaux is not None:
                            junta = juntaaux
                        # self.mwindow.setValText(text,self.termoparctrl)
                        mydict[f"termop{self.termoparctrl}"] = text 
                        self.dman.appendTData(self.termoparctrl,rtimeaux,val)
                        autotermopread = self.termoparctrl

                    # axx = time.time()
                    for k in range(8):
                        if k == autotermopread:
                            pass
                        elif self.enablemap[k]:
                            val,juntaaux,text = self.leTermopar(k)
                            rtimeaux = round((time.time()) - self.starttime,2)
                            if juntaaux is not None:
                                junta = juntaaux                            
                            # self.mwindow.setValText(text,k)
                            mydict[f"termop{k}"] = text
                            self.dman.appendTData(k,rtimeaux,val) 
                        else:
                            self.dman.appendEmptyData(k,readtime)
                    for k in range(2):  
                        if self.enablemap[k+8]:    
                            val,text = self.leADC(k)                  
                            mydict[f"adc{k}"] = text
                    self.dman.incrementCtReadings()  
                    # print(time.time() - axx)             
                    # self.mwindow.setJunta(f"{junta:.2f}  °C")
                    mydict["junta"] = f"{junta:.2f}"



                    # TODO: Readings if auxiliary inputs:
                    # for k in range(8,10):
                    #     if self.enablemap[k]:
                    #         print(f"E{k-8}")

                    # self.mwindow.updatePlot()
                    # self.mwindow.updatePlot()
                    # self.newdata.emit(mydict)
                    # print(mydict)
                    self.statusdict["data"] = mydict
                    self.statusdict["status"] = "valid"
        
            # print("tick")
            slptime = 1.0 - (time.time() - temptime)
            if slptime > 0:
                time.sleep(slptime)       
            # print("tock") 

                    # print(time.time() - axxx)
                    # print(self.Tsample)

                    # QThread.sleep(1)
                    # while not self.flagsampletimeout:
                    #     QThread.msleep(100)
                    # self.flagsampletimeout = False
                    # mutex.lock()
                    # condwait.wait(mutex)
                    # mutex.unlock()
                    # QThread.msleep(500)
                    # print(".")

        
        