import json
import random

PROMPT = "你是一位专业的医疗保险知识问答专家。请用通俗、准确、可执行的方式回答用户关于健康、医疗保险、理赔与投保规则等问题。"
MAX_LENGTH = 2048

def dataset_jsonl_transfer_insurance(origin_path, train_out_path, val_out_path, val_ratio=0.1, seed=42):
    """
    读取 insurance.jsonl（JSON 数组或 JSONL），转换为 instruction/input/output 并切分 train/val
    - instruction 优先使用样本内 system，缺省回退至全局 PROMPT
    - 跳过缺少 output 的样本
    """

    def _load_any_json_or_jsonl(path):
        items = []
        with open(path, "r", encoding="utf-8") as f:
            head = f.read(2048)
            f.seek(0)
            if head.lstrip().startswith("["):
                data = json.load(f)
                if isinstance(data, list):
                    items = data
                else:
                    items = [data]
            else:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    items.append(json.loads(line))
        return items

    raw = _load_any_json_or_jsonl(origin_path)

    examples = []
    for item in raw:
        conv = item.get("conversation", [])
        if not isinstance(conv, list):
            continue
        for turn in conv:
            sys_txt = (turn.get("system") or "").strip() or PROMPT
            usr = (turn.get("input") or "").strip()
            out = (turn.get("output") or "").strip()
            if usr and out:
                examples.append({
                    "instruction": sys_txt,
                    "input": usr,
                    "output": out
                })

    random.Random(seed).shuffle(examples)
    n = len(examples)
    n_val = max(1, int(n * val_ratio)) if n > 0 else 0
    val_examples = examples[:n_val]
    train_examples = examples[n_val:]

    def _dump_jsonl(path, data):
        with open(path, "w", encoding="utf-8") as f:
            for ex in data:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    _dump_jsonl(train_out_path, train_examples)
    _dump_jsonl(val_out_path, val_examples)


if __name__ == "__main__":
    
    dataset_jsonl_transfer_insurance(
        origin_path="insurance.jsonl",
        train_out_path="train_format.jsonl",
        val_out_path="val_format.jsonl",
        val_ratio=0.1,
        seed=42
    )