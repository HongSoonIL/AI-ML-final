import numpy as np
import math
from scipy.signal import savgol_filter

class OneEuroFilter:
    """
    신호의 떨림(Jitter)을 줄이고 시계열 일관성을 유지하기 위한 OneEuro Filter 구현.
    속도가 빠를 때는 지연(Lag)을 줄이고, 느릴 때는 떨림을 제거합니다.
    """
    def __init__(self, t0, x0, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = x0
        self.dx_prev = np.zeros_like(x0)
        self.t_prev = t0

    def smoothing_factor(self, t_e, cutoff):
        r = 2 * math.pi * cutoff * t_e
        return r / (r + 1)

    def exponential_smoothing(self, a, x, x_prev):
        return a * x + (1 - a) * x_prev

    def __call__(self, t, x):
        """
        t: 현재 시간 (혹은 프레임 인덱스)
        x: 현재 관절 좌표 (numpy array)
        """
        t_e = t - self.t_prev
        
        # 1. 변화율(Velocity) 계산 및 필터링
        a_d = self.smoothing_factor(t_e, self.d_cutoff)
        dx = (x - self.x_prev) / t_e if t_e > 0 else np.zeros_like(x)
        dx_hat = self.exponential_smoothing(a_d, dx, self.dx_prev)

        # 2. Cutoff 주파수 적응형 조절
        cutoff = self.min_cutoff + self.beta * np.abs(dx_hat)

        # 3. 신호 필터링
        a = self.smoothing_factor(t_e, cutoff)
        x_hat = self.exponential_smoothing(a, x, self.x_prev)

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t

        return x_hat

def apply_savgol_filter(data, window_length=7, polyorder=3):
    """
    전체 시퀀스에 대해 Savitzky-Golay 필터를 적용하여 부드럽게 만듭니다.
    data: (T, 33, 3) 또는 (T, N)
    """
    # 윈도우 길이는 데이터 길이보다 작고 홀수여야 함
    if len(data) <= window_length:
        print("[경고] 데이터 길이가 윈도우보다 짧아 SavGol 필터를 적용하지 않습니다.")
        return data

    filtered_data = np.zeros_like(data)
    # 각 관절(33개)과 각 축(x,y,z)에 대해 개별 적용
    # data shape이 (T, 33, 3)인 경우
    if data.ndim == 3:
        T, J, D = data.shape
        for j in range(J):
            for d in range(D):
                filtered_data[:, j, d] = savgol_filter(data[:, j, d], window_length, polyorder)
    else:
        # (T, D) 형태인 경우
        D = data.shape[1]
        for d in range(D):
            filtered_data[:, d] = savgol_filter(data[:, d], window_length, polyorder)
            
    return filtered_data

class FootLocking:
    """
    발 미끄러짐(Foot Sliding) 방지 알고리즘.
    발의 속도와 높이를 감지하여 지면에 닿았다고 판단되면 위치를 고정합니다.
    """
    def __init__(self, ground_height=0.05, velocity_threshold=0.005):
        self.ground_height = ground_height        # 발이 이 높이 이하이면 접지로 간주
        self.velocity_threshold = velocity_threshold # 발 속도가 이 이하이면 정지로 간주
        
        # 이전 프레임의 발 위치 저장
        self.prev_left_pos = None
        self.prev_right_pos = None
        
        # 락킹 상태 (True면 고정 중)
        self.left_locked = False
        self.right_locked = False
        
        self.left_lock_pos = None
        self.right_lock_pos = None

    def apply(self, current_pose):
        """
        current_pose: (33, 3) - 현재 프레임의 3D 포즈
        """
        refined_pose = current_pose.copy()
        
        # MediaPipe BlazePose 인덱스: 왼쪽 발(29, 31), 오른쪽 발(30, 32)
        # 여기서는 발목(27, 28)이나 발 뒤꿈치(29, 30) 등을 사용할 수 있으나 
        # 과제 보고서 기준에 맞춰 31(왼발 끝), 32(오른발 끝) 위주로 처리하거나
        # 힐(29, 30)을 기준으로 잡습니다. (보통 29, 30이 힐)
        
        l_idx, r_idx = 29, 30 
        
        l_pos = refined_pose[l_idx]
        r_pos = refined_pose[r_idx]

        # 초기화
        if self.prev_left_pos is None:
            self.prev_left_pos = l_pos
            self.prev_right_pos = r_pos
            return refined_pose

        # 1. 왼쪽 발 처리
        l_vel = np.linalg.norm(l_pos - self.prev_left_pos)
        l_height = l_pos[1] # y가 높이

        # 접지 조건: 높이가 낮고 속도가 느릴 때
        if l_height < self.ground_height and l_vel < self.velocity_threshold:
            if not self.left_locked:
                self.left_locked = True
                self.left_lock_pos = l_pos.copy()
                self.left_lock_pos[1] = 0 # 지면에 완전 밀착 (필요 시)
            
            # 락킹 적용 (x, z 고정, y는 0)
            refined_pose[l_idx] = self.left_lock_pos
            # 발가락 등 주변 관절도 같이 고정해주면 더 좋음 (여기선 단순화)
        else:
            self.left_locked = False
            
        # 2. 오른쪽 발 처리
        r_vel = np.linalg.norm(r_pos - self.prev_right_pos)
        r_height = r_pos[1]

        if r_height < self.ground_height and r_vel < self.velocity_threshold:
            if not self.right_locked:
                self.right_locked = True
                self.right_lock_pos = r_pos.copy()
                self.right_lock_pos[1] = 0
            
            refined_pose[r_idx] = self.right_lock_pos
        else:
            self.right_locked = False

        # 상태 업데이트
        self.prev_left_pos = refined_pose[l_idx]
        self.prev_right_pos = refined_pose[r_idx]

        return refined_pose