

# Begin loading HEX Profile Collection

print('Loading NSLS-II HEX profile collection...')


import time


class FileLoadingTimer:

    def __init__(self):
        self.start_time = 0
        self.loading = False


    def start_timer(self, filename):
        if self.loading:
            raise Exception('File already loading!')

        print(f'Loading {filename}...')
        self.start_time = time.time()
        self.loading = True


    def stop_timer(self, filename):

        elapsed = time.time() - self.start_time
        print(f'Done loading {filename} in {elapsed} seconds.')
        self.loading = False


file_load_timer = FileLoadingTimer()