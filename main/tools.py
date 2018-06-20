import time


def timer(func):
    def wrapper(*args, **kwargs):
        timer_start = time.clock()
        result = func(*args, **kwargs)
        timer_end = time.clock()
        print(f'{func.__name__} executed in {timer_end-timer_start}')
        return result

    return wrapper
