#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

__author__ = "wtp"

"""

from coupled_simulation import utilities as util
import json
import os

class geo_sto:

    '''
    class to include geologic storage simulations

    '''
    def __init__(self, cd):

        # load data.json information into objects dictionary (= attributes of
        # the object)
        path = (cd.working_dir + cd.geostorage_path + cd.scenario +
                '.geostorage_ctrl.json')
        wdir = cd.working_dir + cd.geostorage_path
        with open(path) as f:
            self.__dict__.update(json.load(f))

        #self.tespy_charge_path = wdir + self.tespy_charge_path
        #self.tespy_discharge_path = wdir + self.tespy_discharge_path

        #self.simulator = ''
        #self.simulator_path = ''
        self.working_dir_loc = wdir
        self.keep_ecl_logs = False

        # save the original simulation title in case of eclipse simulation (not needed for e300)
        self.simulation_title_orig = self.simulation_title
        self.current_simulation_title = self.simulation_title
        self.old_simulation_title = self.simulation_title

        if self.retain_ecl_logs == "True":
            self.keep_ecl_logs = True
        else:
            self.keep_ecl_logs = False


    def CallStorageSimulation(self, target_flow, tstep, iter_step, coupling_data, op_mode):
        '''
        Entry point for geo-storage simulation, handles all data transfer, executes simulator
        and provides simulation results to power plant simulator

        :param target_flow: target storage flow rate in sm3/d; 15.5556°C, 1 atm
        :param type: float
        :param tstep: current timestep
        :param type: int
        :param tstepsize: length of current timestep
        :param type: float
        :param op_mode: current operational mode, either 'charging', 'discharging' or 'shut-in'
        :param type: str
        :returns: returns tuple of new pressure at the well (in reservoir) and actual (achieved) storage flow rate
        '''
        #this is the entry point for the geostorage coupling

        if(self.simulator == 'ECLIPSE' or self.simulator == 'e300'):
            flowrate, pressure = self.RunECLIPSE(target_flow, tstep, iter_step, coupling_data.t_step_length, op_mode)
        elif self.simulator == 'proxy':
            pass
            #implement later
        else:
            print('ERROR: simulator flag not understood. Is: ', self.simulator)

        return pressure, flowrate


    def RunECLIPSE(self, target_flowrate, tstep, iter_step, tstepsize, current_mode):
        '''
        Function acting as a wrapper for using eclipse (SChlumberger) as a storage simulator

        :param target_flowrate: target storage flow rate in sm3/d; 15.5556°C, 1 atm
        :param type: float
        :param tstep: current timestep
        :param type: int
        :param tstepsize: length of current timestep
        :param type: float
        :param op_mode: current operational mode, either 'charging', 'discharging' or 'shut-in'
        :param type: str
        :returns: returns tuple of new pressure at the well (in reservoir) and actual (achieved) storage flow rate
        '''

        #set simulation title
        if iter_step == 0:
            #print ( 'iteration: keeping title')
            self.old_simulation_title = self.current_simulation_title

        if current_mode == 'init':
            self.current_simulation_title = self.simulation_title_orig + '_TSTEP_INIT'
            os.rename(self.working_dir_loc + self.simulation_title_orig  + '.DATA', self.working_dir_loc + self.current_simulation_title + '.DATA')
        else:
            if iter_step == 0:
                self.current_simulation_title = self.simulation_title_orig + '_TSTEP_' + str(tstep)
                os.rename(self.working_dir_loc + self.old_simulation_title + '.DATA', self.working_dir_loc + self.current_simulation_title + '.DATA')

        if not current_mode == 'init':
            print('Running storage simulation')
            print('Dir: ', self.working_dir_loc)
            print('SimTitle: ', self.current_simulation_title + '.DATA')
            print('Timestep/iteration:\t\t', '%.0f'%tstep, '/', '%.0f'%iter_step)
            print('Timestep size:\t\t\t', tstepsize, '\t\ts')
            print('Target storage flowrate:\t', '%.6f'%target_flowrate, '\tkg/s')
            print('\t\t\t\t', '%.6f'%(target_flowrate / self.surface_density), '\tsm3/s')
            print('Operational mode:\t\t', current_mode)

        else:
            print('Running storage simulation to obtain initial pressure')

        #adjusting to surface volume rates
        target_flowrate = target_flowrate / self.surface_density

        # assembling current ecl data file
        self.reworkECLData(tstep, tstepsize, target_flowrate, current_mode)
        # executing eclipse
        self.ExecuteECLIPSE(tstep, iter_step, current_mode)
        # reading results
        ecl_results = self.GetECLResults(tstep, current_mode)

        #adjusting to mass flow rates
        ecl_results[1] = ecl_results[1] * self.surface_density

        if not current_mode == 'init':
            print('----------------------------------------------------------------------------------------------------------------')
            print('Pressure actual:\t\t', '%.6f'%ecl_results[0], '\tbars')
            print('Flowrate actual:\t\t', '%.6f'%ecl_results[1], '\tkg/s')
            print('\t\t\t\t', '%.6f'%(ecl_results[1] / self.surface_density), '\tsm3/s')
        else:
            print('Initial pressure is: \t', '%.6f'%ecl_results[0], 'bars')
        print('----------------------------------------------------------------------------------------------------------------')
        return (ecl_results[1], ecl_results[0])


    def rearrangeRSMDataArray(self, rsm_list):
        '''
        Function to sort through Eclipse's RSM file and obtain well data from last timestep

        :param rsm_list: list containing the RSM file
        :param type: str
        :returns: returns a clearer version of the input list (type: list of strings)
        '''
        # function to re-order / get rid off line breaks etc. in input
        break_count = util.getStringCount(rsm_list, 'SUMMARY OF RUN')
        break_positions = util.getStringPositions(rsm_list, 'SUMMARY OF RUN')
        #break_positions = [i for i, s in enumerate(rsm_list) if 'SUMMARY OF RUN' in s]

        if break_count > 0:
            interval = break_positions[1] - break_positions[0]

        output = []

        for i in range(break_count):
            for j in range(interval):
                current_idx = i * interval + j
                if i == 0:
                    temp = rsm_list[current_idx][:-3]
                    output.append(rsm_list[i])
                if j > 1:
                    #print('current_idx: ', current_idx)
                    temp1 = str(output[j]).replace('\n', '')
                    temp1 = temp1[:-3]
                    temp2 = str(rsm_list[current_idx])
                    temp2 = temp2[:-3]
                    temp2 += '\n'
                    temp = temp1 + temp2
                    temp = temp.replace('\t\t', '\t')

                    output[j] = temp
        #delete first two (empty) entries
        del output[0]
        del output[0]

        return output


    def reworkECLData(self, timestep, timestepsize, flowrate, op_mode):
        '''
        function to change settings in the eclipse input file required for the storage simulation

        :param timestep: current timestep of simulation
        :param type: int
        :param timestepsize: length of current timestep
        :param type: float
        :param flowrate: current target storage flow rate from power plant simulation
        :param type: float
        :param op_mode: current operational mode, either 'charging', 'discharging' or 'shut-in'
        :param type: str
        :returns: no return value
        '''
        # open and read eclipse data file
        ecl_data_file = util.getFile(self.working_dir_loc + self.current_simulation_title + '.DATA')
        #print(self.working_dir_loc + self.simulation_title + '.DATA')
        #print ('rework ecl data tstep:', timestep)
        #rearrange the entries in the saved list
        if timestep == 1:
            #look for EQUIL and RESTART keyword
            equil_pos = util.searchSection(ecl_data_file, 'EQUIL')
            if(equil_pos > 0):
                #delete equil and replace with restart
                #assemble new string for restart section
                ecl_data_file[equil_pos] = 'RESTART\n'
                ecl_data_file[equil_pos + 1] =  '\'' + self.old_simulation_title + '\' \t'
                ecl_data_file[equil_pos + 1] += str(int(self.restart_id) + timestep )  + ' /\n'
            else:
                restart_pos = util.searchSection(ecl_data_file, "RESTART")
                if restart_pos > 0:
                    #assemble new string for restart section
                    ecl_data_file[restart_pos + 1] =  '\'' + self.old_simulation_title + '\' \t'
                    ecl_data_file[restart_pos + 1] += str(int(self.restart_id) + timestep)  + ' /\n'
        if timestep > 1:
            restart_pos = util.searchSection(ecl_data_file, "RESTART")
            if restart_pos > 0:
                #assemble new string for restart section
                ecl_data_file[restart_pos + 1] =  '\'' + self.old_simulation_title + '\' \t'
                ecl_data_file[restart_pos + 1] += str(int(self.restart_id) + timestep )  + ' /\n'
                print('Assembled string for restart:')
                print('\'' + self.old_simulation_title + '\'', str(int(self.restart_id) + timestep )  + ' /\n')
                print( 'Restart id: ', self.restart_id, ' timestep: ', timestep)

        #now rearrange the well schedule section
        schedule_pos = util.searchSection(ecl_data_file, "WCONINJE")
        if schedule_pos == -1:
            schedule_pos = util.searchSection(ecl_data_file, "WCONPROD")

        #print(schedule_pos)

        if schedule_pos > 0:
            # delete the old well schedule
            del ecl_data_file[schedule_pos:]
            # append new well schedule
            # first calculate rate applied for each well
            well_count = len(self.well_names)
            well_target = abs(flowrate / well_count) / self.reservoir_compartments
            well_target_days = well_target * 60.0 * 60.0 *24.0

            #now construct new well schedule section
            #ecl_data_file.append('\n')

            if op_mode == 'charging':
                ecl_data_file.append("WCONINJE\n")
                for idx in range(len(self.well_names)):
                    line = '\'' + self.well_names[idx] + '\''
                    line += '\t\'GAS\'\t\'OPEN\'\t\'RATE\'\t'
                    line += str(well_target_days) + '\t'
                    line += '1*\t' + str(self.well_upper_BHP[idx]) + '/\n'
                    ecl_data_file.append(line)

            elif op_mode == 'discharging':
                ecl_data_file.append("WCONPROD\n")
                for idx in range(len(self.well_names)):
                    line = '\'' + self.well_names[idx] + '\''
                    line += '\t\'OPEN\'\t\'GRAT\'\t1*\t1*\t'
                    line += str(well_target_days) + '\t'
                    line += '1*\t1*\t' + str(self.well_lower_BHP[idx]) + '/\n'
                    ecl_data_file.append(line)

            elif op_mode == 'shut-in' or op_mode == 'init':
                ecl_data_file.append("WCONINJE\n")
                for idx in range(len(self.well_names)):
                    line = '\'' + self.well_names[idx] + '\''
                    line += '\t\'GAS\'\t\'OPEN\'\t\'RATE\'\t'
                    line += '0.0' + '\t'
                    line += '1*\t' + str(self.well_upper_BHP[idx]) + '/\n'
                    ecl_data_file.append(line)
            else:
                print('ERROR: operational mode not understood in timestep: ', timestep, ' is: ', op_mode)

            ecl_data_file.append('/')
            #finish schedule
            timestepsize_days = timestepsize / 60.0 / 60.0 / 24.0
            file_finish = ['\n', '\n', 'TSTEP\n', '1*' + str(timestepsize_days) + '\n', '/\n', '\n', '\n', 'END\n' ]
            ecl_data_file += file_finish


            #save to new file
            #if not op_mode == 'init':
            #    temp_path = self.working_dir_loc + self.current_simulation_title + '.DATA'
            #else:
            #    #print('ini mode')
            #    temp_path = self.working_dir_loc + self.simulation_title + '_init.DATA'
            temp_path = self.working_dir_loc + self.current_simulation_title + '.DATA'
            util.writeFile(temp_path, ecl_data_file)


    def deleteSimFiles(self, tstep):

        file_ending_unform = ".X"
        file_ending_form = ".F"
        temp_nr_str = ""

        if tstep == 0:
            temp_nr_str = "0001"
        else:
            if tstep > -1:
                tstep + 1

            if (tstep + 1) <= 10:
                temp_nr_str = "000" + str(tstep)
            elif (tstep + 1) <= 100:
                temp_nr_str = "00" + str(tstep)
            elif (tstep + 1) <= 1000:
                temp_nr_str = "0" + str(tstep)
            else:
                temp_nr_str =  str(tstep)

        file_ending_unform += temp_nr_str
        file_ending_form += temp_nr_str

        #if tstep > -1:
            #print('Attempting to delete file: *', file_ending, ' in timestep ', tstep)

        termination_list = [
            self.working_dir_loc + self.old_simulation_title + file_ending_form,
            self.working_dir_loc + self.old_simulation_title + file_ending_unform,
            self.working_dir_loc + self.old_simulation_title + ".DBG",
            self.working_dir_loc + self.old_simulation_title + ".dbprtx",
            self.working_dir_loc + self.old_simulation_title + ".ECLEND",
            self.working_dir_loc + self.old_simulation_title + ".ECLRUN",
            self.working_dir_loc + self.old_simulation_title + ".GRID",
            self.working_dir_loc + self.old_simulation_title + ".FGRID",
            self.working_dir_loc + self.old_simulation_title + ".h5",
            self.working_dir_loc + self.old_simulation_title + ".INIT",
            self.working_dir_loc + self.old_simulation_title + ".FINIT",
            self.working_dir_loc + self.old_simulation_title + ".INSPEC",
            self.working_dir_loc + self.old_simulation_title + ".FINSPEC",
            self.working_dir_loc + self.old_simulation_title + ".LOG",
            self.working_dir_loc + self.old_simulation_title + ".MSG",
            self.working_dir_loc + self.old_simulation_title + ".RSSPEC",
            self.working_dir_loc + self.old_simulation_title + ".FRSSPEC",
            self.working_dir_loc + self.old_simulation_title + ".SMSPEC",
            self.working_dir_loc + self.old_simulation_title + ".FSMSPEC",
            self.working_dir_loc + self.old_simulation_title + ".UNSMRY",
            self.working_dir_loc + self.old_simulation_title + ".FUNSMRY",
        ]
        for entry in termination_list:
            #print('Deleting: ', entry)
            util.deleteFile(entry)


    def ExecuteECLIPSE(self, tstep, iter_step, op_mode):
        '''
        Function to call eclipse executable

        :param tstep: current timestep
        :param type: int
        :param op_mode: operational mode of storage simulation
        :param type: str
        :returns: no return value
        '''
        #import subprocess
        #import os

        if os.name == 'nt':
            simulation_path = ''
            simulation_path = self.working_dir_loc  + self.current_simulation_title + '.DATA'
            #if not op_mode == 'init':
            #    simulation_path = self.working_dir_loc  + self.current_simulation_title + '.DATA'
            #else:
            #    simulation_path = self.working_dir_loc  + self.simulation_title + '_init.DATA'

            if self.keep_ecl_logs == True:
                log_file_path = self.working_dir_loc + 'log_' + self.current_simulation_title + '_' + str(tstep) + '_' + str(iter_step) + '.txt'
            else:
                log_file_path = 'NUL'
            temp = 'eclrun ' + self.simulator + ' ' + simulation_path + ' >' + log_file_path
            os.system(temp)
        #elif os.name == 'posix':
            #log_output_loc += ' &'
            #rc = subprocess.call(['eclrun', simulator_loc, simulation_title_loc, '>', log_output_loc])

        #print(rc)


    def GetECLResults(self, timestep, current_op_mode):
        '''
        Function to get the eclipse results from the *.RSM file and analyze the results

        :param timestep: current timestep
        :param type: int
        :param current_op_mode: operational mode, either 'charging', 'discharging' or 'shut-in'
        :param type: str
        :returns: returns a tuple of float values containing pressure and actual storage flow rate
        '''

        #first read the results file
        #if not current_op_mode == 'init':
        #    filename = self.working_dir_loc + self.simulation_title + '.RSM'
        #else:
        #    filename = self.working_dir_loc + self.simulation_title + '_init.RSM'
        filename = self.working_dir_loc + self.current_simulation_title + '.RSM'
        results = util.getFile(filename)
        #sort the rsm data to a more uniform dataset
        reorderd_rsm_data = self.rearrangeRSMDataArray(results)
        #print(reorderd_rsm_data)
        #eleminate additional whitespaces, duplicate entries, etc.
        well_results = util.contractDataArray(reorderd_rsm_data)
        #print(well_results)
        
        # check number of data entries in well_results:
        
        entry_count_temp = 0
        if self.simulator == 'e300':
            entry_count_temp = 4
        elif self.simulator == 'ECLIPSE':
            entry_count_temp = 5
        values = len(well_results) - entry_count_temp
        if values > 1:
            print('Warning: possible loss of data, too many data lines in RSM file')

        #data structures to save the flowrates, pressures and names of all individual wells
        well_pressures = []
        well_flowrates_days = []
        well_flowrates = []
        well_names = []
        well_names_loc = []
        flowrate_actual = 0.0
        pressure_actual = 0.0

        # get well pressures
        pressure_keyword = 'WBHP'
        bhp_positions = util.getStringPositions(well_results[0], pressure_keyword)

        for i in bhp_positions:
            well_pressures.append(float(well_results[-1][i]))
            well_names.append(well_results[2][i])
            if well_pressures[-1] == 0.0:
                print('Problem: well pressure for well ', well_names[-1], ' is zero. Setting to corresponding BHP limit' )
                bhp_limits_well = self.getWellBHPLimits(well_names[-1])
                if current_op_mode == 'discharging':
                    well_pressures[-1] = bhp_limits_well[0]
                elif current_op_mode == 'charging' or current_op_mode == 'shut-in':
                    well_pressures[-1] = bhp_limits_well[1]
                else:
                    print('Problem: could not determine operational mode, assuming injection')
                    well_pressures[-1] = bhp_limits_well[1]


        # now get well flow rates
        if current_op_mode == 'discharging': #negative flow rates
            #get all positions of WGPR entries in well_results
            flow_keyword = 'WGPR'
            flow_positions = util.getStringPositions(well_results[0], flow_keyword)
            for i in flow_positions:
                well_flowrates_days.append(float(well_results[-1][i]))
                well_names_loc.append(well_results[2][i])

        elif current_op_mode == 'charging': #positive flow rates
            flow_keyword = 'WGIR'
            flow_positions = util.getStringPositions(well_results[0], flow_keyword)
            for i in flow_positions:
                well_flowrates_days.append(float(well_results[-1][i]))
                well_names_loc.append(well_results[2][i])

        elif current_op_mode == 'shut-in' or current_op_mode == 'init':
            #do nothing
            pass
        else:
            print('Warning: operational mode not understood, assuming shut-in at timestep: ', timestep)

        if ( current_op_mode == 'charging' or current_op_mode == 'discharging'):
            # go through well names list and compare strings.
            # rearrange if necessary to get correct match for pressures and flowrates
            correct_idx = []
            for i in range(len(well_names)):
                if well_names[i] == well_names_loc[i]:
                    correct_idx.append(i)
                else:
                    target_str = well_names[i]
                    for j in range(len(well_names_loc)):
                        if well_names_loc[j] == target_str:
                            correct_idx.append(j)
            #sort entries in well_flowrates based on correct_idx
            well_flowrates_temp = well_flowrates_days
            for i in correct_idx:
                well_flowrates_days[i] = well_flowrates_temp[i]

            #calculate total flowrate
            #maybe add timestep dependence (only needed if more than one per call)?
            #change unit of flowrates to sm3/s from sm3/d
            for i in range(len(well_flowrates_days)):
                well_flowrates.append(well_flowrates_days[i] / 60.0 / 60.0 / 24.0)


            flowrate_actual = sum(well_flowrates)

            if flowrate_actual > 0.0 :
                #calculate average pressure
                pressure_actual = 0.0
                for i in range(len(well_pressures)):
                    pressure_actual += well_pressures[i] * well_flowrates[i]
                pressure_actual = pressure_actual / flowrate_actual
            else:
                pressure_actual = sum(well_pressures) / float(len(well_pressures))
        else:
            pressure_actual = sum(well_pressures) / float(len(well_pressures))

        return [pressure_actual, flowrate_actual]

    def getWellBHPLimits(self, well_name):
        '''
        function to obtain pressure limits for a given well
        :param well_name: well identifier used to search well list
        :param type: string
        :returns: tuple of float, lower and upper BHP limit
        '''
        for i in range(len(self.well_names)):
            if self.well_names[i] == well_name:
                return [self.well_lower_BHP[i], self.well_upper_BHP[i]]

        return [0.0, 0.0]




