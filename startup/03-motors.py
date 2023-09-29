from ophyd import EpicsMotor, Device
from ophyd import Component as Cpt

class SampleTower(Device):
    x1 = Cpt(EpicsMotor, "X1}Mtr")
    z1 = Cpt(EpicsMotor, "Z1}Mtr")
    pitch = Cpt(EpicsMotor, "Rx}Mtr")
    vertical_y = Cpt(EpicsMotor, "Y}Mtr")
    roll = Cpt(EpicsMotor, "Rz}Mtr")
    

    def get_axis_pos(self, motor_name):
        motor = getattr(self, motor_name)
        return motor.read()[motor.name]['value']
    
    


class HEXMonochromator(Device):

    xtal2_z = Cpt(EpicsMotor, "Z2}Mtr")

mono = HEXMonochromator("XF:27IDA-OP:1{Mono:DCLM-Ax:", name="mono")
sample_tower = SampleTower("XF:27IDF-OP:1{SMPL:1-Ax:", name="sample_tower")
