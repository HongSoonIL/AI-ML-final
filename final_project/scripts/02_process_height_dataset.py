"""
학습 데이터 생성 스크립트: BlazePose 높이 보정

이 스크립트는 BlazePose의 원본 키포인트 데이터로부터 학습 데이터를 생성합니다.

데이터 설계 전략:
-----------------
1. 입력 데이터 (X): BlazePose 원본 키포인트 (높이 정보가 부정확함)
2. 정답 데이터 (Y): 물리적 제약조건을 적용하여 높이를 보정한 키포인트

핵심 아이디어:
-------------
BlazePose는 단안 카메라로부터 3D 포즈를 추정하기 때문에 깊이(높이) 정보가 부정확합니다.
특히 다음과 같은 문제가 발생합니다:
- 발이 지면 아래로 떨어지는 현상
- 서 있는 자세에서도 높이가 흔들림
- 점프/착지 시 비현실적인 높이 변화

해결 방법:
---------
발 키포인트를 기준으로 지면 레벨을 계산하고, 모든 키포인트의 높이를
지면 기준으로 정규화합니다. 이는 물리적으로 타당한 3D 포즈를 생성합니다.

Self-Supervised Learning:
------------------------
별도의 ground truth 데이터 없이, BlazePose 출력 자체에서 물리적 제약조건을
활용하여 정답 데이터를 자동 생성합니다.
"""

import os
import numpy as np
import pandas as pd
from glob import glob
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from utils.viser_test import PoseViser

RAW_KEYPOINTS_DIR = os.path.join(ROOT, "data", "raw_keypoints")
OUT_DIR = os.path.join(ROOT, "data", "processed")

os.makedirs(OUT_DIR, exist_ok=True)


def load_raw_keypoints(npz_path):
    """
    BlazePose 원본 키포인트 데이터를 로드합니다.
    
    BlazePose는 33개의 신체 랜드마크를 추출하며, 각 랜드마크는
    3D 좌표 (x, y, z)와 가시성(visibility) 정보를 가집니다.
    
    Args:
        npz_path: BlazePose 키포인트가 저장된 .npz 파일 경로
    
    Returns:
        numpy.ndarray: (T, 33, 3) 형태의 키포인트 시퀀스
            - T: 프레임 수
            - 33: BlazePose 키포인트 개수
            - 3: (x, y, z) 좌표
    """
    data = np.load(npz_path, allow_pickle=True)["data"]
    df = pd.DataFrame(data, columns=["frame","landmark","x","y","z","visibility"])

    pts_seq = []

    for f, group in df.groupby("frame"):
        group = group.sort_values("landmark")
        pts = group[["x","y","z"]].values  # (33,3)
        pts_seq.append(pts)

    return np.array(pts_seq)   # (T,33,3)


def create_height_corrected_target(raw_seq):
    """
    물리적 제약조건을 적용하여 높이 보정된 정답 데이터를 생성합니다.
    
    이 함수는 Self-Supervised Learning의 핵심으로, 별도의 ground truth 없이
    물리 법칙을 활용하여 정답 데이터를 자동 생성합니다.
    
    알고리즘:
    --------
    1. 발 키포인트 (31번: 왼발, 32번: 오른발) 중 낮은 쪽을 지면 레벨로 설정
    2. 모든 키포인트의 Y 좌표를 지면 기준(Y=0)으로 정규화
    3. 음수 높이값을 0으로 클램핑 (지면 침투 방지)
    
    물리적 제약조건:
    --------------
    - 발은 항상 지면(Y=0)에 있어야 함
    - 다른 신체 부위는 지면 위에 있어야 함 (Y >= 0)
    - 중력의 영향을 받아 지면 아래로 떨어질 수 없음
    
    Args:
        raw_seq: (T, 33, 3) BlazePose 원본 키포인트
    
    Returns:
        numpy.ndarray: (T, 33, 3) 높이 보정된 키포인트
    
    예시:
    ----
    입력 (원본 BlazePose):
        발 높이: -0.05, 머리 높이: 1.65
    
    출력 (보정 후):
        발 높이: 0.00, 머리 높이: 1.70  (상대 높이 유지)
    """
    seq = raw_seq.copy()

    # BlazePose 발 키포인트 인덱스
    # 33개 키포인트 중 31번: 왼쪽 발목, 32번: 오른쪽 발목
    LEFT_FOOT = 31
    RIGHT_FOOT = 32

    # Step 1: 지면 레벨 계산
    # 각 프레임에서 왼발과 오른발 중 더 낮은 쪽을 지면으로 간주
    # 이는 한쪽 발이 들려있을 때도 지면 레벨을 정확히 계산하기 위함
    foot_y = np.minimum(seq[:, LEFT_FOOT, 1], seq[:, RIGHT_FOOT, 1])  # (T,)
    
    # Shape 변환: (T,) → (T, 1) → broadcasting to (T, 33)
    frame_ground = foot_y[:, None]

    # Step 2: 높이 정규화 (지면 = 0)
    # 모든 키포인트의 Y 좌표에서 지면 레벨을 빼서 상대 높이로 변환
    seq[:, :, 1] -= frame_ground

    # Step 3: 물리적 제약 적용 (지면 침투 방지)
    # 음수 높이를 0으로 클램핑하여 키포인트가 지면 아래로 떨어지지 않도록 함
    seq[:, :, 1] = np.maximum(seq[:, :, 1], 0)

    return seq


def main():
    """
    학습 데이터 생성 메인 파이프라인
    
    프로세스:
    --------
    1. raw_keypoints/ 폴더에서 BlazePose .npz 파일 로드
    2. 각 비디오에 대해:
       - 입력 데이터 (X): 원본 키포인트 저장 → *_raw.npy
       - 정답 데이터 (Y): 높이 보정된 키포인트 저장 → *_target.npy
    
    출력 형식:
    ---------
    - *_raw.npy: (T, 33, 3) - 입력 데이터
    - *_target.npy: (T, 33, 3) - 정답 데이터
    
    학습 시에는 (T, 33, 3) → (T, 99)로 평탄화하여 사용합니다.
    """
    paths = glob(f"{RAW_KEYPOINTS_DIR}/*.npz")
    print("=" * 80)
    print("학습 데이터 생성 시작")
    print("=" * 80)
    print(f"\n원본 키포인트 파일 수: {len(paths)}\n")

    for i, path in enumerate(paths, 1):
        base = os.path.basename(path).replace(".npz", "")
        print(f"[{i}/{len(paths)}] 처리 중: {base}")

        # -------------------------------
        # 1) Load raw BlazePose sequence
        # -------------------------------
        # BlazePose에서 추출한 원본 키포인트 로드
        # 이것이 학습 시 입력 데이터 (X)가 됩니다.
        raw_seq = load_raw_keypoints(path)      # (T,33,3)
        raw_out_path = os.path.join(OUT_DIR, f"{base}_raw.npy")
        np.save(raw_out_path, raw_seq)
        print(f"  → 입력 데이터 저장: {base}_raw.npy (shape: {raw_seq.shape})")

        # ---------------------------------------
        # 2) Create height-corrected target (GT)
        # ---------------------------------------
        # 물리적 제약조건을 적용하여 정답 데이터 생성
        # 이것이 학습 시 정답 데이터 (Y)가 됩니다.
        target_seq = create_height_corrected_target(raw_seq)
        target_out_path = os.path.join(OUT_DIR, f"{base}_target.npy")
        np.save(target_out_path, target_seq)
        print(f"  → 정답 데이터 저장: {base}_target.npy (shape: {target_seq.shape})")
        
        # 통계 출력
        print(f"  → 프레임 수: {len(raw_seq):,}")
        print(f"  → 학습 샘플 수: {len(raw_seq):,}")
        print()

    print("=" * 80)
    print("학습 데이터 생성 완료!")
    print(f"출력 디렉토리: {OUT_DIR}")
    print("=" * 80)
    print("\n다음 단계: python src/train.py 를 실행하여 모델 학습")

    # IF you want to visualize the output
    # vis = PoseViser(fps=30)
    # raw = np.load("./data/processed/Dimitrov_Slow_Motion_Forehand_target.npy")
    # vis.play_sequence(raw)


if __name__ == "__main__":
    main()
