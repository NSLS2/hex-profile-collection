

class GeRMDetector(Device):

    count = Cpt(EpicsSignal, ".CNT",kind=Kind.omitted)
    mca = Cpt(EpicsSignal, ".MCA", kind=Kind.hinted)
    number_of_channels = Cpt(EpicsSignal, ".NELM", kind=Kind.config)
    gain = Cpt(EpicsSignal, ".GAIN", kind=Kind.config)
    shaping_time = Cpt(EpicsSignal, ".SHPT", kind = Kind.config)
    count_time = Cpt(EpicsSignal, ".TP", kind = Kind.config)
    auto_time = Cpt(EpicsSignal, ".TP1", kind=Kind.config)
    run_num = Cpt(EpicsSignal, ".RUNNO",kind=Kind.omitted)
    fast_data_filename = Cpt(EpicsSignal, ".FNAM", string=True)
    operating_mode = Cpt(EpicsSignal, ".MODE",kind=Kind.omitted)
    single_auto_toggle = Cpt(EpicsSignal, ".CONT",kind=Kind.omitted)
    Cpt(EpicsSignal, ".GMON",kind=Kind.omitted)
    ip_addr = Cpt(EpicsSignal, ".IPADDR", string=True)
    temp_1 = Cpt(EpicsSignal, ":Temp1", kind = Kind.omitted)
    temp_2 = Cpt(EpicsSignal, ":Temp2", kind=Kind.omitted)
    fpga_cpu_temp = Cpt(EpicsSignal, ":ztmp",kind=Kind.omitted)
    calibration_file = Cpt(EpicsSignal, ".CALF",kind=Kind.omitted)
    multi_file_supression = Cpt(EpicsSignal, ".MFS",kind=Kind.omitted)
    tdc = Cpt(EpicsSignal, ".TDC",kind=Kind.omitted)
    leakage_pulse = Cpt(EpicsSignal, ".LOAO",kind=Kind.omitted)
    internal_leak_curr = Cpt(EpicsSignal, ".EBLK",kind=Kind.omitted)
    pileup_rejection = Cpt(EpicsSignal, ".PUEN",kind=Kind.omitted)
    test_pulse_aplitude = Cpt(EpicsSignal, ".TPAMP",kind=Kind.omitted)
    channel = Cpt(EpicsSignal, ".MONCH",kind=Kind.omitted)
    tdc_slope = Cpt(EpicsSignal, ".TDS",kind=Kind.omitted)
    test_pulse_freq = Cpt(EpicsSignal, ".TPFRQ",kind=Kind.omitted)
    tdc_mode = Cpt(EpicsSignal, ".TDM",kind=Kind.omitted)
    test_pulce_enable = Cpt(EpicsSignal, ".TPENB",kind=Kind.omitted)
    test_pulse_count = Cpt(EpicsSignal, ".TPCNT",kind=Kind.omitted)
    input_polarity = Cpt(EpicsSignal, ".POL",kind=Kind.omitted)
    voltage = Cpt(EpicsSignal, ":HV_RBV",kind=Kind.omitted)
    current = Cpt(EpicsSignal, ":HV_CUR",kind=Kind.omitted)
    peltier_2 = Cpt(EpicsSignal, ":P2",kind=Kind.omitted)
    peliter_2_current = Cpt(EpicsSignal, ":P2_CUR",kind=Kind.omitted)
    peltier_1 = Cpt(EpicsSignal, ":P1",kind=Kind.omitted)
    peltier_1_current = Cpt(EpicsSignal, ":P1_CUR",kind=Kind.omitted)
    hv_bias = Cpt(EpicsSignal, ":HV",kind=Kind.omitted)
    ring_hi = Cpt(EpicsSignal, ":DRFTHI",kind=Kind.omitted)
    ring_lo = Cpt(EpicsSignal, ":DRFTLO",kind=Kind.omitted)


    save_path = f"{DATA_ROOT}/{CYCLE}/{PROPOSAL}"


    def trigger(self):

        def is_done(value, old_value, **kwargs):
            if old_value == 1 and value == 0:
                return True

            return False

        
        status = SubscriptionStatus(self.count, run=False, callback = is_done)

        self.count.put(1)
        return status


    def describe(self):
        desc = super().describe()
        return desc
        

    def write_mca_hdf5(self):
        mca = self.mca.get()
        print(mca)    


#    def write_tdc_hdf5(self):


# Intialize the GeRM detector ophyd object
germ_detector = GeRMDetector("XF:27ID1-ES{GeRM-Det:1}", name="GeRM")



