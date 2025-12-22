import numpy as np
import tensorflow as tf
import os
import glob
import pandas as pd
import sys

# 경로 설정
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils.filters import OneEuroFilter, apply_savgol_filter, FootLocking
from utils.motion_analysis import analyze_and_plot
from utils.viser_test import PoseViser

# 모델 경로
MODEL_PATH = os.path.join(ROOT, "experiments", "height_mlp_model")

def load_trained_model():
    if not os.path.exists(MODEL_PATH):
        print(f"❌ 모델을 찾을 수 없습니다: {MODEL_PATH}")
        sys.exit(1)
    return tf.keras.models.load_model(MODEL_PATH)

def process_sequence(raw_path, model, output_dir):
    """
    전체 파이프라인:
    Raw Load -> 1. OneEuro(Jitter제거) -> 2. Model(높이보정) -> 3. FootLocking(미끄러짐방지) -> 4. Analysis
    """
    base_name = os.path.basename(raw_path).replace("_raw.npy", "")
    print(f"\n🚀 처리 시작: {base_name}")

    # 1. 데이터 로드
    raw_seq = np.load(raw_path) # (T, 33, 3)
    T, J, D = raw_seq.shape

    # ---------------------------------------------------------
    # 단계 1: OneEuro Filter (신호 전처리 - 입력단 노이즈 제거)
    # ---------------------------------------------------------
    print("  Step 1: OneEuro Filter 적용 중...")
    one_euro_seq = np.zeros_like(raw_seq)
    
    # 33개 관절 각각에 대해 필터 인스턴스 생성
    filters = [OneEuroFilter(t0=0, x0=raw_seq[0, i], min_cutoff=0.5, beta=0.05) for i in range(J)]
    
    for t in range(T):
        for i in range(J):
            one_euro_seq[t, i] = filters[i](t, raw_seq[t, i])

    # ---------------------------------------------------------
    # 단계 2: 모델 추론 (높이 보정)
    # ---------------------------------------------------------
    print("  Step 2: MLP 모델 높이 보정 중...")
    # 모델 입력 형태 (Batch, 99)로 변환
    x_input = one_euro_seq.reshape(T, -1)
    y_pred = model.predict(x_input, verbose=0)
    model_out_seq = y_pred.reshape(T, 33, 3)

    # ---------------------------------------------------------
    # 단계 3: Foot Sliding 방지 및 후처리
    # ---------------------------------------------------------
    print("  Step 3: Foot Sliding 방지 알고리즘 적용 중...")
    final_seq = np.zeros_like(model_out_seq)
    foot_locker = FootLocking(ground_height=0.04, velocity_threshold=0.015)

    for t in range(T):
        # Foot Locking 적용
        final_seq[t] = foot_locker.apply(model_out_seq[t])

    # 추가: 전체적으로 너무 튀는 구간이 있다면 마지막으로 약한 SavGol 적용 (선택사항)
    # final_seq = apply_savgol_filter(final_seq, window_length=5, polyorder=2)

    # ---------------------------------------------------------
    # 결과 저장
    # ---------------------------------------------------------
    refined_npy_path = os.path.join(output_dir, f"{base_name}_refined.npy")
    np.save(refined_npy_path, final_seq)
    
    # CSV 저장 (Unity용)
    csv_rows = []
    for t in range(T):
        for b in range(J):
            x, y, z = final_seq[t, b]
            csv_rows.append([t, b, x, y, z, 1.0])
            
    df = pd.DataFrame(csv_rows, columns=["frame","landmark","x","y","z","visibility"])
    csv_path = os.path.join(output_dir, f"{base_name}_refined.csv")
    df.to_csv(csv_path, index=False)
    print(f"  💾 저장 완료: {csv_path}")

    # ---------------------------------------------------------
    # 단계 4: 모션 분석 (그래프 출력)
    # ---------------------------------------------------------
    print("  Step 4: 모션 분석 그래프 생성 중...")
    analysis_dir = os.path.join(output_dir, "analysis")
    analyze_and_plot(raw_seq, final_seq, analysis_dir, filename_prefix=base_name)

    return raw_seq, final_seq

def main():
    # 경로 설정
    TEST_DATA_PATH = os.path.join(ROOT, "data", "test_keypoints")
    OUTPUT_PATH = os.path.join(ROOT, "data", "output")
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # 모델 로드
    model = load_trained_model()

    # 모든 테스트 파일 처리
    raw_files = glob.glob(f"{TEST_DATA_PATH}/*_raw.npy")
    if not raw_files:
        print("⚠️ 처리할 _raw.npy 파일이 없습니다. scripts/03_create_test_keypoints.py를 먼저 실행하세요.")
        return

    last_raw = None
    last_refined = None

    for raw_path in raw_files:
        last_raw, last_refined = process_sequence(raw_path, model, OUTPUT_PATH)

    # 마지막 결과 시각화 (Web Viser)
    if last_raw is not None:
        print("\n👀 Viser 시각화를 실행합니다...")
        vis = PoseViser(fps=30)
        vis.play_two_sequences(last_raw, last_refined, offset=1.0) # offset: 두 캐릭터 간격

if __name__ == "__main__":
    main()