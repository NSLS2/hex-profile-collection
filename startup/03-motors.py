"""
Ophyd objects for motors

"""

import epics
from ophyd import EpicsMotor, Device
from ophyd import Component as Cpt


class SampleTower(Device):
    """
    Ophyd objects for the sample-tower motors (<-> CSS names):
    """

    # Define a list of objects corresponding to motors of the sample tower    
    axis_x1 = Cpt(EpicsMotor, "X1}Mtr")
    axis_z1 = Cpt(EpicsMotor, "Z1}Mtr")
    pitch = Cpt(EpicsMotor, "Rx}Mtr")
    vertical_y = Cpt(EpicsMotor, "Y}Mtr")
    roll = Cpt(EpicsMotor, "Rz}Mtr")

    x2 = Cpt(EpicsMotor, "X2}Mtr")
    z2 = Cpt(EpicsMotor, "Z2}Mtr")

    rx1 = Cpt(EpicsMotor, "Rx1}Mtr")    
    ry1 = Cpt(EpicsMotor, "Ry1}Mtr")
    rz1 = Cpt(EpicsMotor, "Rz1}Mtr")

    def get_motor_list(self):
        motor_list = []
        for name in self.read_attrs:
            if "." not in name:
                motor_list.append(name)
        return motor_list

    def get_position(self, motor_name):
        try:
            motor = getattr(self, motor_name)
            return motor.read()[motor.name]['value']
        except AttributeError:
            return "No such motor name: {}!".format(motor_name)

    def get_velocity(self, motor_name):
        try:
            motor = getattr(self, motor_name)
            return motor.velocity.value
        except AttributeError:
            return "No such motor name: {}!".format(motor_name)
    
    def get_acceleration(self, motor_name):
        try:
            motor = getattr(self, motor_name)
            return motor.acceleration.value
        except AttributeError:
            return "No such motor name: {}!".format(motor_name)
    
    def get_css_name(self, motor_name):
        try:
            motor = getattr(self, motor_name)
            css_name = epics.caget(motor.prefix + ".DESC") # To be replaced by EpicsSignal
            return css_name
        except AttributeError:
            return "No such motor name: {}!".format(motor_name)
   

class HEXMonochromator(Device):

    xtal2_z = Cpt(EpicsMotor, "Z2}Mtr")

mono = HEXMonochromator("XF:27IDA-OP:1{Mono:DCLM-Ax:", name="mono")
sample_tower = SampleTower("XF:27IDF-OP:1{SMPL:1-Ax:", name="sample_tower")
