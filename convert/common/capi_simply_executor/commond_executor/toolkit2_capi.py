import sys
import os
import re
import numpy as np

realpath = os.path.abspath(__file__)
_sep = os.path.sep
realpath = realpath.split(_sep)

binary_dir = '{}/capi_tools/toolkit2/rknn_capi_test/install'.format(_sep.join(realpath[: realpath.index('convert')+1]))
scaling_file = os.path.join(realpath[0]+_sep, *realpath[1:realpath.index('common')]) + '/capi_tools/scaling_frequency.sh'

require_map = {
    'android':{
        'RK3566': os.path.join(binary_dir, 'rk356x/Android/rknn_capi_test'),
        'RK3568': os.path.join(binary_dir, 'rk356x/Android/rknn_capi_test'),
        'RK3588': os.path.join(binary_dir, 'rk3588/Android/rknn_capi_test'),
        'RK3562': os.path.join(binary_dir, 'rk356x/Android/rknn_capi_test'),
    },
    'linux':{
        'RK3566': os.path.join(binary_dir, 'rk356x/Linux/rknn_capi_test'),
        'RK3568': os.path.join(binary_dir, 'rk356x/Linux/rknn_capi_test'),
        'RK3588': os.path.join(binary_dir, 'rk3588/Linux/rknn_capi_test'), 
        'RV1106': os.path.join(binary_dir, 'rv110x/Linux/rknn_capi_test'),
        'RV1103': os.path.join(binary_dir, 'rv110x/Linux/rknn_capi_test'), 
        'RK3562': os.path.join(binary_dir, 'rk356x/Linux/rknn_capi_test'),
    },
}

rk35xx_api_dict = {
    'normal': 'rknn_capi_test',
    'zero_copy': 'rknn_capi_test_zero_copy',
}

rv110x_api_dict = {
    'zero_copy': 'rknn_capi_test_zero_copy_NC1HWC2',
    # 'zero_copy': 'rknn_capi_test_zero_copy_NCHW',
}


_debug = True
def my_os_system(cmd):
    if _debug:
        return os.system(cmd)
    else:
        return os.system(cmd + ' > /dev/null 2>&1')


def root_adb():
    pass



class tk2_capi_executor(object):
    # --------------------------------------------------------------------------------------------------
    # Capi type: normal
    #       feature:
    #           1.multi-input available
    #           2.float/uint8 allow
    #           3.output get as float
    #       return:
    #           1.npy result
    #           2.(rknn)input_set cost time
    #           3.(rknn)run cost time
    #           4.(rknn)output_get cost time
    #
    #
    # Capi type: zero_copy
    #       feature:
    #           1.only support single input
    #           2.only allow uint8 input
    #           3.output get as uint8, but using cpu dequantize output to float32
    #       return:
    #           1.npy result
    #           2.(rknn)input sync cost time
    #           3.(rknn)run cost time
    #           4.(rknn)output_sync cost time
    #           5.cpu dequantize time
    #
    # --------------------------------------------------------------------------------------------------
    def __init__(self, model_path, model_config_dict, device_system):
        self.model_path = model_path
        self.model_config_dict = model_config_dict
        self.device_system = device_system

        self.platform = model_config_dict.get('RK_device_platform', 'RK3566').upper()
        if self.platform not in ['RK3566', 'RK3568', 'RK3588', 'RV1106', 'RV1103', 'RK3562']:
            raise Exception('Unsupported platform: {}'.format(self.platform))
        else:
            print("\n  Device: {}".format(self.platform))

        # setting api map
        if self.platform.upper() in ['RK3566', 'RK3568', 'RK3588', 'RK3562']:
            self.api_dict = rk35xx_api_dict
        elif self.platform.upper() in ['RV1106', 'RV1103']:
            self.api_dict = rv110x_api_dict

        if self.device_system == 'android':
            self.remote_tmp_path = '/data/capi_test/'
        #     my_os_system("adb root & adb remount")
        else:
            if self.platform.upper() in ['RV1106', 'RV1103']:
                self.remote_tmp_path = '/tmp/capi_test'
                # clear remote path
                my_os_system("adb shell rm -r {}".format(self.remote_tmp_path))
            else:
                self.remote_tmp_path = '/userdata/capi_test/'
                # self.remote_tmp_path = '/tmp/capi_test'

        self.test_model_name = 'test.rknn'

        self.input_name = ['{}.npy'.format(i+1) for i in range(len(model_config_dict['inputs']))]
        self.input_line = '#'.join(self.input_name)

        self.capi_record_file_name = 'capi_record.txt'

        self.remote_output_name = None
        self.output_name = None

        self._check_file()
        self._push_model()

        self.scaling_freq()


    def scaling_freq(self):
        my_os_system("adb push {} {}".format(scaling_file, self.remote_tmp_path))
        if self.device_system == 'android':
            my_os_system("adb shell chmod 777 {}/scaling_frequency.sh".format(self.remote_tmp_path))
            my_os_system("adb shell {}/scaling_frequency.sh -c {}".format(self.remote_tmp_path, self.platform.lower()))
        else:
            my_os_system("adb shell chmod 777 {}/scaling_frequency.sh".format(self.remote_tmp_path))
            my_os_system("adb shell bash {}/scaling_frequency.sh -c {}".format(self.remote_tmp_path, self.platform.lower()))


    def _get_output_name(self, number):
        self.remote_output_name = []
        self.output_name = []
        for i in range(number):
            self.remote_output_name.append(os.path.join(self.remote_tmp_path, 'output_{}.npy'.format(i)) )
            self.output_name.append('output_{}.npy'.format(i))


    def _push_input(self, inputs):
        print('---> push input')
        in_keys = list(self.model_config_dict['inputs'].keys())
        for i in range(len(inputs)):
            tmp_path = os.path.join(self.result_store_dir, self.input_name[i])
            inputs_info = self.model_config_dict['inputs'][in_keys[i]]
            in_shape = list(inputs[i].shape)
            define_shape = inputs_info['shape']

            if len(in_shape) == 3 and len(define_shape) == 4:
                # hwc -> nhwc
                inputs[i] = inputs[i].reshape(1, *in_shape)
                in_shape = list(inputs[i].shape)

            if len(in_shape) == 4 and len(define_shape) == 4:
                if in_shape == define_shape:
                    # nchw -> nhwc
                    inputs[i] = inputs[i].transpose(0, 2, 3, 1)

                elif list(inputs[i].transpose(0,3,1,2).shape) == define_shape:
                    # already nhwc
                    pass
                else:
                    print("WARNING capi get input shape as {}, but defined input shape is {}".format(in_shape, define_shape))
                    print("This may lead to wrong result")
                    pass
            np.save(tmp_path, inputs[i])
            my_os_system("adb push {} {}".format(tmp_path, os.path.join(self.remote_tmp_path, self.input_name[i])))
        

    def _check_file(self):
        # file_state = my_os_system("adb shell '(ls {} && echo exists) || (echo miss)'".format(self.remote_tmp_path))
        # if file_state == 'miss':
        self._push_require()


    def _push_require(self):
        # TODO smart push
        # import subprocess
        # result = subprocess.getoutput("adb shell md5sum {xxx}")
        print('---> push require')
        my_os_system("adb shell mkdir {}".format(self.remote_tmp_path))
        my_os_system("adb shell sync")
        my_os_system("adb push {}/* {}".format(require_map[self.device_system.lower()][self.platform.upper()], self.remote_tmp_path))


    def _push_model(self):
        print('---> push model')
        my_os_system("adb push {} {}".format(self.model_path, self.remote_tmp_path))
        self.test_model_name = os.path.basename(self.model_path)

    def _run_command(self, loop, api_type):
        if api_type in self.api_dict:
            # TODO record ddr
            command_in_shell = [
                'cd {}'.format(self.remote_tmp_path),
                'chmod 777 {}'.format(self.api_dict[api_type]),
                'export LD_LIBRARY_PATH={}/lib'.format(self.remote_tmp_path),
                # 'echo 3 > /proc/irq/25/smp_affinity_list',
                # 'sync && echo 3 > /proc/sys/vm/drop_caches',
                # 'taskset 8 ./{} {} {} {} {}'.format(self.api_dict[api_type], 
                #             self.test_model_name, 
                #             self.input_line, 
                #             loop, 
                #             self.model_config_dict['core_mask']),
                './{} {} {} {} {}'.format(self.api_dict[api_type], 
                                          self.test_model_name, 
                                          self.input_line, 
                                          loop, 
                                          self.model_config_dict['core_mask']),
            ]
            if self.platform.upper() in ['RV1106', 'RV1103']:
                command_in_shell = ['RkLunch-stop.sh'] + command_in_shell
            running_command = ' adb shell "\n {}"'.format("\n ".join(command_in_shell))                
            my_os_system(running_command)
        else:
            raise Exception('Unsupported api_type: {}'.format(api_type))

    def _init_time_dict(self, api_type='normal'):
        if api_type == 'normal':
            self.time_dict = {
                'model_init': 0,
                'input_set': 0,
                'run': 0,
                'output_get': 0,
            }
        elif api_type == 'zero_copy':
            self.time_dict = {
                'model_init': 0,
                'input_io_init': 0,
                'output_io_init': 0,
                'run': 0,
            }

    def _pull_and_parse(self, api_type):
        my_os_system("adb pull {} {}".format(os.path.join(self.remote_tmp_path, self.capi_record_file_name), self.result_store_dir))

        self._init_time_dict(api_type)
        with open(os.path.join(self.result_store_dir, self.capi_record_file_name), 'r') as f:
            lines = f.readlines()

        assert len(lines)>0, "{} is blank, run failed".format(self.capi_record_file_name)
        pattern = re.compile(r'\d+')
        output_number = int(pattern.findall(lines[1])[0])

        for _l in lines:
            p_name = _l.split(':')[0]
            if p_name in self.time_dict:
                self.time_dict[p_name] = float('.'.join(pattern.findall(_l)))

        self._get_output_name(output_number)
        for i in range(len(self.output_name)):
            my_os_system("adb pull {} {}".format(os.path.join(self.remote_tmp_path, self.output_name[i]), self.result_store_dir))
        capi_result = []
        for i in range(len(self.output_name)):
            capi_result.append(np.load(os.path.join(self.result_store_dir, self.output_name[i])))
        return capi_result, self.time_dict


    def _clear(self):
        print('---> clear and create result store dir')
        self.result_store_dir = './tmp'
        if os.path.exists(self.result_store_dir):
            files = os.listdir(self.result_store_dir)
            for _f in files:
                if _f == 'fake_in':
                    continue
                my_os_system("rm -r {}".format(os.path.join(self.result_store_dir,_f)))
        if not os.path.exists(self.result_store_dir):
            os.makedirs(self.result_store_dir)

    def _clear_remote(self, full=False):
        print('---> clear remote record.txt')
        my_os_system('adb shell rm {}'.format(os.path.join(self.remote_tmp_path, self.capi_record_file_name)))
        if full is True:
            # my_os_system('adb shell rm {}'.format(os.path.join(self.remote_tmp_path, self.test_model_name)))
            my_os_system('adb shell rm {}'.format(os.path.join(self.remote_tmp_path, '*.npy')))

    def execute(self, inputs, loop, api_type):
        self._clear()
        self._clear_remote()
        self._push_input(inputs)
        self._run_command(loop, api_type)
        capi_result, time_set = self._pull_and_parse(api_type)

        self._clear_remote(True)
        return capi_result, time_set


if __name__ == '__main__':
    etk = tk2_capi_executor('./', {})
    etk._run_command(1, 'normal')
