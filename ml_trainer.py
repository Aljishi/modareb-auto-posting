import os
import json
import requests
import numpy as np
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("API_KEY")
API_URL = os.environ.get("API_URL", "https://app.sahmk.sa/api/v1")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

MODEL_FILE   = "data/ml_model.json"
DATASET_FILE = "data/training_data.json"

TASI_SYMBOLS = [
    "1010","1020","1030","1050","1060","1080","1120","1150",
    "2010","2020","2030","2060","2080","2090","2100","2110",
    "2120","2130","2150","2160","2170","2180","2190","2200",
    "2210","2220","2222","2223","2230","2240","2250","2290",
    "2310","2320","2330","2340","2350","2360","2370","2380",
    "4001","4002","4005","4007","4009","4020","4030","4031",
    "4040","4050","4061","4100","4150","4160","4170","4180",
    "4190","4200","4210","4220","4230","4240","4250","4261",
    "4300","4320","4321","4322","4323","4324","4327","4328",
    "5010","5020","5110","6001","6010","6013","6020","6040",
    "7010","7020","7030","7040","7203","7204",
    "8010","8020","8030","8040","8050","8060","8070","8100",
    "9516","9526","9527","9528","9529","9536","9543","9544",
    "9545","9546","9547","9548","9549","9553","9554","9555",
]


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def get(endpoint, params=None):
    try:
        r = requests.get(
            f"{API_URL}{endpoint}",
            headers=HEADERS,
            params=params or {},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  error {endpoint}: {e}")
    return None


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period-1) + gains[i]) / period
        avg_loss = (avg_loss * (period-1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain/avg_loss)), 2)


def calc_ema(closes, period):
    if len(closes) < period:
        return closes[-1] if closes else 0
    k   = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for p in closes[period:]:
        ema = p * k + ema * (1 - k)
    return round(ema, 4)


def calc_atr(highs, lows, closes, period=14):
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i]  - closes[i-1])
        )
        trs.append(tr)
    if not trs:
        return 0
    atr = sum(trs[:period]) / min(period, len(trs))
    for tr in trs[period:]:
        atr = (atr*(period-1) + tr) / period
    return round(atr, 4)


def calc_bollinger_width(closes, period=20):
    if len(closes) < period:
        period = len(closes)
    recent = closes[-period:]
    mid    = sum(recent) / period
    std    = (sum((c-mid)**2 for c in recent) / period) ** 0.5
    return round((std*4) / mid if mid > 0 else 0, 4)


def find_support_resistance(highs, lows, closes):
    if len(highs) < 5:
        price = closes[-1]
        return price * 1.03, price * 0.97
    resistances, supports = [], []
    for i in range(1, len(highs)-1):
        if highs[i] >= highs[i-1] and highs[i] >= highs[i+1]:
            resistances.append(highs[i])
    for i in range(1, len(lows)-1):
        if lows[i] <= lows[i-1] and lows[i] <= lows[i+1]:
            supports.append(lows[i])
    price      = closes[-1]
    above      = [r for r in resistances if r > price * 1.002]
    resistance = min(above) if above else max(highs)
    below      = [s for s in supports if s < price * 0.998]
    support    = max(below) if below else min(lows)
    return round(resistance, 4), round(support, 4)


def extract_features(hist):
    closes  = hist["closes"]
    highs   = hist["highs"]
    lows    = hist["lows"]
    volumes = hist["volumes"]

    if len(closes) < 10:
        return None

    price = closes[-1]
    if price <= 0:
        return None

    rsi   = calc_rsi(closes)
    ema20 = calc_ema(closes, min(20, len(closes)))
    ema50 = calc_ema(closes, min(50, len(closes)))
    atr   = calc_atr(highs, lows, closes)

    atr_pct  = (atr / price * 100) if price > 0 else 0
    bb_width = calc_bollinger_width(closes)

    resistance, support = find_support_resistance(highs, lows, closes)
    dist_to_resistance  = (resistance - price) / price * 100
    dist_to_support     = (price - support) / price * 100

    avg_vol_5  = sum(volumes[-5:])  / 5  if len(volumes) >= 5  else volumes[-1]
    avg_vol_10 = sum(volumes[-10:]) / 10 if len(volumes) >= 10 else volumes[-1]
    vol_ratio  = avg_vol_5 / avg_vol_10 if avg_vol_10 > 0 else 1

    chg_1d  = (closes[-1] - closes[-2])  / closes[-2]  * 100 if len(closes) >= 2  else 0
    chg_3d  = (closes[-1] - closes[-4])  / closes[-4]  * 100 if len(closes) >= 4  else 0
    chg_5d  = (closes[-1] - closes[-6])  / closes[-6]  * 100 if len(closes) >= 6  else 0
    chg_10d = (closes[-1] - closes[-11]) / closes[-11] * 100 if len(closes) >= 11 else 0

    day_range = highs[-1] - lows[-1]
    close_pos = (closes[-1] - lows[-1]) / day_range if day_range > 0 else 0.5

    price_vs_ema20 = (price - ema20) / ema20 * 100 if ema20 > 0 else 0
    price_vs_ema50 = (price - ema50) / ema50 * 100 if ema50 > 0 else 0

    up_days_5 = sum(1 for i in range(-5, 0)
                    if len(closes) > abs(i) and closes[i] > closes[i-1])

    return {
        "rsi":                round(rsi, 2),
        "atr_pct":            round(atr_pct, 2),
        "bb_width":           round(bb_width, 4),
        "dist_to_resistance": round(dist_to_resistance, 2),
        "dist_to_support":    round(dist_to_support, 2),
        "vol_ratio":          round(vol_ratio, 2),
        "chg_1d":             round(chg_1d, 2),
        "chg_3d":             round(chg_3d, 2),
        "chg_5d":             round(chg_5d, 2),
        "chg_10d":            round(chg_10d, 2),
        "close_pos":          round(close_pos, 2),
        "price_vs_ema20":     round(price_vs_ema20, 2),
        "price_vs_ema50":     round(price_vs_ema50, 2),
        "up_days_5":          up_days_5,
        "price":              price,
    }


def make_label(closes, future_days=5, target_pct=3.0):
    if len(closes) < future_days + 1:
        return None
    entry      = closes[-(future_days+1)]
    future_max = max(closes[-future_days:])
    return 1 if (future_max - entry) / entry * 100 >= target_pct else 0


def fetch_historical(symbol, period=60):
    data = get(f"/historical/{symbol}/", {"period": period})
    if not data:
        return None
    history = data.get("data", [])
    if len(history) < 15:
        return None
    history = sorted(history, key=lambda x: x.get("date",""))
    return {
        "closes":  [safe_float(d.get("close"))  for d in history],
        "highs":   [safe_float(d.get("high"))   for d in history],
        "lows":    [safe_float(d.get("low"))     for d in history],
        "volumes": [safe_float(d.get("volume"))  for d in history],
        "dates":   [d.get("date","")             for d in history],
        "count":   len(history),
    }


class SimpleDecisionTree:
    def __init__(self, max_depth=5, min_samples=3):
        self.max_depth   = max_depth
        self.min_samples = min_samples
        self.tree        = None

    def _gini(self, labels):
        if not labels:
            return 0
        n  = len(labels)
        p1 = sum(labels) / n
        p0 = 1 - p1
        return 1 - p1**2 - p0**2

    def _best_split(self, X, y, features):
        best_gain   = 0
        best_feat   = None
        best_thresh = None
        parent_gini = self._gini(y)

        for feat in features:
            values = sorted(set(row[feat] for row in X))
            for i in range(len(values)-1):
                thresh  = (values[i] + values[i+1]) / 2
                left_y  = [y[j] for j, row in enumerate(X) if row[feat] <= thresh]
                right_y = [y[j] for j, row in enumerate(X) if row[feat] > thresh]

                if not left_y or not right_y:
                    continue

                n    = len(y)
                gain = parent_gini - (
                    len(left_y)/n  * self._gini(left_y) +
                    len(right_y)/n * self._gini(right_y)
                )

                if gain > best_gain:
                    best_gain   = gain
                    best_feat   = feat
                    best_thresh = thresh

        return best_feat, best_thresh, best_gain

    def _build(self, X, y, depth):
        if not y or depth >= self.max_depth or len(y) < self.min_samples:
            return {"leaf": True, "prob": sum(y)/len(y) if y else 0.5}
        if len(set(y)) == 1:
            return {"leaf": True, "prob": float(y[0])}

        features = list(X[0].keys())
        feat, thresh, gain = self._best_split(X, y, features)

        if feat is None or gain < 0.001:
            return {"leaf": True, "prob": sum(y)/len(y)}

        left_idx  = [i for i, row in enumerate(X) if row[feat] <= thresh]
        right_idx = [i for i, row in enumerate(X) if row[feat] > thresh]

        return {
            "leaf":   False,
            "feat":   feat,
            "thresh": thresh,
            "left":   self._build([X[i] for i in left_idx],  [y[i] for i in left_idx],  depth+1),
            "right":  self._build([X[i] for i in right_idx], [y[i] for i in right_idx], depth+1),
        }

    def fit(self, X, y):
        self.tree = self._build(X, y, 0)

    def _predict_one(self, node, x):
        if node["leaf"]:
            return node["prob"]
        if x[node["feat"]] <= node["thresh"]:
            return self._predict_one(node["left"],  x)
        else:
            return self._predict_one(node["right"], x)

    def predict_proba(self, X):
        return [self._predict_one(self.tree, x) for x in X]


class SimpleRandomForest:
    def __init__(self, n_trees=20, max_depth=5):
        self.n_trees   = n_trees
        self.max_depth = max_depth
        self.trees     = []

    def _bootstrap(self, X, y):
        import random
        n   = len(X)
        idx = [random.randint(0, n-1) for _ in range(n)]
        return [X[i] for i in idx], [y[i] for i in idx]

    def fit(self, X, y):
        import random
        all_features = list(X[0].keys())
        n_features   = max(3, int(len(all_features)**0.5))

        self.trees = []
        for _ in range(self.n_trees):
            Xb, yb   = self._bootstrap(X, y)
            selected = random.sample(all_features, n_features)
            Xb_sub   = [{f: row[f] for f in selected} for row in Xb]
            tree     = SimpleDecisionTree(max_depth=self.max_depth)
            tree.fit(Xb_sub, yb)
            self.trees.append((tree, selected))

        print(f"  تدريب {self.n_trees} شجرة مكتمل ✅")

    def predict_proba(self, x):
        probs = []
        for tree, features in self.trees:
            x_sub = {f: x[f] for f in features if f in x}
            prob  = tree.predict_proba([x_sub])[0]
            probs.append(prob)
        return sum(probs) / len(probs) if probs else 0.5

    def to_dict(self):
        return {
            "n_trees":   self.n_trees,
            "max_depth": self.max_depth,
            "trees":     [{"tree": t.tree, "features": f} for t, f in self.trees]
        }

    @classmethod
    def from_dict(cls, data):
        rf = cls(data["n_trees"], data["max_depth"])
        rf.trees = []
        for item in data["trees"]:
            t      = SimpleDecisionTree(data["max_depth"])
            t.tree = item["tree"]
            rf.trees.append((t, item["features"]))
        return rf


def collect_training_data():
    print("\n" + "="*60)
    print("جمع بيانات التدريب...")
    print("="*60)

    dataset = []
    success = 0
    failed  = 0

    for i, sym in enumerate(TASI_SYMBOLS):
        hist = fetch_historical(sym, period=60)
        if not hist or hist["count"] < 20:
            failed += 1
            continue

        closes  = hist["closes"]
        highs   = hist["highs"]
        lows    = hist["lows"]
        volumes = hist["volumes"]

        for window_end in range(15, len(closes) - 5):
            window = {
                "closes":  closes[:window_end],
                "highs":   highs[:window_end],
                "lows":    lows[:window_end],
                "volumes": volumes[:window_end],
            }
            features = extract_features(window)
            if features is None:
                continue
            label = make_label(closes[:window_end + 6], future_days=5, target_pct=3.0)
            if label is None:
                continue
            features["symbol"] = sym
            features["label"]  = label
            dataset.append(features)

        success += 1
        if (i+1) % 10 == 0:
            print(f"  [{i+1}/{len(TASI_SYMBOLS)}] {success} سهم ✅ | {len(dataset)} sample")

    print(f"\n  اجمالي: {success} سهم | {len(dataset)} sample للتدريب")
    if dataset:
        print(f"  نسبة الإيجابي: {sum(d['label'] for d in dataset)/len(dataset)*100:.1f}%")

    with open(DATASET_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False)

    return dataset


def train_model(dataset):
    print("\n" + "="*60)
    print("تدريب النموذج...")
    print("="*60)

    FEATURES = [
        "rsi", "atr_pct", "bb_width",
        "dist_to_resistance", "dist_to_support",
        "vol_ratio", "chg_1d", "chg_3d", "chg_5d", "chg_10d",
        "close_pos", "price_vs_ema20", "price_vs_ema50", "up_days_5",
    ]

    X = [{f: d[f] for f in FEATURES} for d in dataset]
    y = [d["label"] for d in dataset]

    split   = int(len(X) * 0.8)
    X_train = X[:split]; X_test = X[split:]
    y_train = y[:split]; y_test = y[split:]

    print(f"  Train: {len(X_train)} | Test: {len(X_test)}")

    model = SimpleRandomForest(n_trees=20, max_depth=5)
    model.fit(X_train, y_train)

    correct = 0
    tp = fp = tn = fn = 0

    for x, true_label in zip(X_test, y_test):
        prob       = model.predict_proba(x)
        pred_label = 1 if prob >= 0.5 else 0
        if pred_label == true_label: correct += 1
        if pred_label == 1 and true_label == 1: tp += 1
        if pred_label == 1 and true_label == 0: fp += 1
        if pred_label == 0 and true_label == 0: tn += 1
        if pred_label == 0 and true_label == 1: fn += 1

    accuracy  = correct / len(X_test) * 100 if X_test else 0
    precision = tp / (tp+fp) * 100 if (tp+fp) > 0 else 0
    recall    = tp / (tp+fn) * 100 if (tp+fn) > 0 else 0

    print(f"\n  النتائج:")
    print(f"  Accuracy : {accuracy:.1f}%")
    print(f"  Precision: {precision:.1f}%")
    print(f"  Recall   : {recall:.1f}%")
    print(f"  TP:{tp} FP:{fp} TN:{tn} FN:{fn}")

    model_data = {
        "model":      model.to_dict(),
        "features":   FEATURES,
        "accuracy":   round(accuracy, 2),
        "precision":  round(precision, 2),
        "recall":     round(recall, 2),
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "samples":    len(dataset),
        "is_default": False,
    }

    with open(MODEL_FILE, "w", encoding="utf-8") as f:
        json.dump(model_data, f, ensure_ascii=False, indent=2)

    print(f"\n  النموذج محفوظ في {MODEL_FILE} ✅")
    return model, model_data


def create_default_model():
    """
    ✅ إنشاء نموذج افتراضي محايد إذا لم يكن ml_model.json موجوداً
    يعطي 50.0 لجميع الأسهم — يُستبدل بنموذج حقيقي بعد weekly-report
    """
    default = {
        "model":      {"n_trees": 0, "max_depth": 5, "trees": []},
        "features":   [
            "rsi", "atr_pct", "bb_width",
            "dist_to_resistance", "dist_to_support",
            "vol_ratio", "chg_1d", "chg_3d", "chg_5d", "chg_10d",
            "close_pos", "price_vs_ema20", "price_vs_ema50", "up_days_5",
        ],
        "accuracy":   50.0,
        "precision":  50.0,
        "recall":     50.0,
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "samples":    0,
        "is_default": True,
    }
    os.makedirs("data", exist_ok=True)
    with open(MODEL_FILE, "w", encoding="utf-8") as f:
        json.dump(default, f, ensure_ascii=False, indent=2)
    return default


def predict(symbol, hist):
    """
    يستخدم النموذج المحفوظ للتنبؤ بسهم جديد
    يُستدعى من fetch_api_data.py
    """
    try:
        # ✅ إذا النموذج غير موجود أنشئ نموذجاً افتراضياً محايداً
        if not os.path.exists(MODEL_FILE):
            create_default_model()
            return 50.0

        with open(MODEL_FILE, "r", encoding="utf-8") as f:
            model_data = json.load(f)

        # نموذج افتراضي — أرجع 50 مباشرة بدون حساب
        if model_data.get("is_default") or not model_data["model"].get("trees"):
            return 50.0

        features = extract_features(hist)
        if features is None:
            return 50.0

        model    = SimpleRandomForest.from_dict(model_data["model"])
        prob     = model.predict_proba(features)
        ml_score = round(prob * 100, 1)

        return ml_score

    except Exception:
        return 50.0


def main():
    if not API_KEY:
        print("API_KEY missing")
        return

    dataset = collect_training_data()

    if len(dataset) < 100:
        print("بيانات غير كافية للتدريب")
        return

    model, stats = train_model(dataset)

    print(f"\n{'='*60}")
    print("النموذج جاهز!")
    print(f"  الدقة    : {stats['accuracy']}%")
    print(f"  Precision: {stats['precision']}%")
    print(f"  Samples  : {stats['samples']}")
    print(f"  تاريخ    : {stats['trained_at']}")


if __name__ == "__main__":
    main()
