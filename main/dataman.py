import numpy as np
import pandas as pd


class dataman:


    def __init__(self,maxtime=360,tsampling=1):
        self.maxtime = maxtime
        self.totpoints = int(maxtime*60/tsampling)
        self.TData = []
        self.TTime = [] 
        self.ctsample = []       
        for k in range(8):
            self.TData.append(np.empty(self.totpoints))
            self.TData[-1].fill(np.nan)
            self.TTime.append(np.zeros(self.totpoints))
            self.ctsample.append(0)
        self.globalctreadings = 0
        self.setpoint = None


    def resetData(self,tsampling=1):
        self.totpoints = int(self.maxtime*60/tsampling)
        for k in range(8):
            self.TData.append(np.empty(self.totpoints))
            self.TData[-1].fill(np.nan)
            self.TTime[k] = np.zeros(self.totpoints)
            self.ctsample[k] = 0
        self.globalctreadings = 0

    
    def appendTData(self,idx,time,val):
        self.TData[idx][self.ctsample[idx]] = val
        self.TTime[idx][self.ctsample[idx]] = time
        self.ctsample[idx] += 1


    def appendEmptyData(self,idx,time):
        # self.TData[idx][self.ctsample[idx]] = np.nan
        self.TTime[idx][self.ctsample[idx]] = time
        self.ctsample[idx] += 1

    
    def incrementCtReadings(self):
        self.globalctreadings += 1

    
    def saveFile(self,filepath):

        if self.globalctreadings == 0:
            raise Exception("Nothing to save!")

        hasData = [True] * 8
        cttermops = 0
        columns = []
        for k in range(8):
            if np.all(np.isnan(self.TData[k][:self.globalctreadings])):
                hasData[k] = False
            else:
                columns.append(f"Tempo{k+1}")
                columns.append(f"Termopar{k+1}")
                cttermops += 1

        if True not in hasData:
            raise Exception("Nothing to save!!!")

        mydata = np.zeros((self.globalctreadings,cttermops*2))
        ctt = 0
        for k in range(8):
            if hasData[k]:
                mydata[:,ctt] = self.TTime[k][:self.globalctreadings]
                mydata[:,ctt+1] = self.TData[k][:self.globalctreadings]
                ctt += 2        

        dataframe = pd.DataFrame(mydata,columns=columns)
        dataframe.to_csv(filepath,sep=";",decimal=",",index=False)
        

        
