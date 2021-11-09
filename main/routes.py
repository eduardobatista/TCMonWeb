from pathlib import Path
from . import main
from flask import current_app,send_file,send_from_directory,abort,render_template,request
from datetime import datetime
import json

@main.route('/')
def entrance():
    return render_template('main.html')

@main.route('/startstop',methods=['POST'])
def startstop():
    if current_app.driver.flagrunning:
        current_app.driver.paraLeituras()
        return "Parando leituras."
    else: 
        fenable = request.values.getlist("flagenable[]") + ["false","false"]
        port = request.values["port"]
        termoptype = request.values["termoptype"]
        for k in range(10):
            fenable[k] = (fenable[k] == "true")
        kp = float(request.values["kp"])
        ki = float(request.values["ki"])
        kd = float(request.values["kd"])
        mode = request.values["mode"]        
        ctrltermop = int(request.values["ctrltermop"])
        setpoint = float(request.values["setpoint"])
        manuallevel = float(request.values["manuallevel"])
        current_app.driver.setCtrlConfig(mode,ctrltermop,kp,ki,kd)
        if mode == "auto":
            current_app.driver.changeSetPoint(setpoint)
        elif mode == "manual":
            current_app.driver.changeManualCtrlLevel(manuallevel)
        current_app.driver.iniciaLeituras(1,fenable,termoptype,port)
        return "Iniciando leituras."

@main.route('/status',methods=['POST'])
def status():
    return current_app.driver.statusdict

@main.route('/cleardata',methods=['POST'])
def cleardata():
    current_app.driver.limpaLeituras()
    return "Dados apagados..."

@main.route('/command',methods=['POST'])
def command():
    cmd = request.values["cmd"]
    if cmd == "saveUIstate":
        with open(Path(current_app.MAINPATH,"uistate.conf"),'w') as ff:
            ff.write(request.values["data"])
            return "UI state salvo."
    elif cmd == "getUIstate":
        with open(Path(current_app.MAINPATH,"uistate.conf"),'r') as ff:
            return ff.read()
    elif cmd == "changeCtrl":
        mode = request.values["mode"]        
        setpoint = float(request.values["setpoint"])
        manuallevel = float(request.values["manuallevel"])
        current_app.driver.changeCtrlType(mode)
        if mode == "auto":
            current_app.driver.changeSetPoint(setpoint)
        elif mode == "manual":
            current_app.driver.changeManualCtrlLevel(manuallevel)
    elif cmd == "getData":    
        gct = current_app.driver.dman.globalctreadings
        if gct == 0:
            return "NoData"
        else:
            fenable = request.values.getlist("flagenable[]")
            for k in range(8):
                fenable[k] = (fenable[k] == "true")
            retdict = {} 
            retdict["x"] = []
            retdict["y"] = []            
            for k in range(8):
                if fenable[k]:
                    retdict["x"].append(list(current_app.driver.dman.TTime[k][:gct]))
                    retdict["y"].append(list(current_app.driver.dman.TData[k][:gct]))
            return json.dumps(retdict)
    return current_app.driver.statusdict

@main.route('/savefile')
def savedata():
    fname = datetime.now().strftime("%Y-%m-%d_%H_%M_%S") + ".csv"
    workdir = current_app.MAINPATH / "work"
    if not workdir.exists():
        workdir.mkdir()
    try:
        current_app.driver.dman.saveFile(workdir / fname)
        return send_file(workdir / fname, as_attachment=True, cache_timeout=0)
    except Exception as ex:
        return str(ex)
    # return fname