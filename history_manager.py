import os
import json
import pandas as pd
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HISTORY_DIR = ".history"

class HistoryManager:
    def __init__(self, history_dir=HISTORY_DIR):
        self.history_dir = history_dir
        os.makedirs(self.history_dir, exist_ok=True)
        logging.info(f"✅ 初始化历史记录目录：{self.history_dir}")

    def get_history(self):
        metas = []
        for name in os.listdir(self.history_dir):
            folder_path = os.path.join(self.history_dir, name)
            if not os.path.isdir(folder_path):
                continue
            meta_file_path = os.path.join(folder_path, "meta.json")
            if not os.path.exists(meta_file_path):
                logging.warning(f"⚠️ 跳过无元数据的目录：{folder_path}")
                continue
            try:
                with open(meta_file_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                metas.append(meta)
                logging.debug(f"📥 成功加载元数据：{meta_file_path}")
            except Exception as e:
                logging.error(f"❌ 加载元数据失败（{meta_file_path}）：{str(e)}")
                continue
        metas.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        logging.info(f"📊 共加载 {len(metas)} 条历史导入记录")
        return metas

    def get_data(self, meta):
        crawl_folder = os.path.join(self.history_dir, meta["timestamp"])
        data_file_path = os.path.join(crawl_folder, "data.csv")
        anno_file_path = os.path.join(crawl_folder, "annotations.json")

        df = pd.DataFrame()
        jama = []
        gqs = []
        discern = []
        custom_data = {}

        if os.path.exists(data_file_path):
            try:
                df = pd.read_csv(data_file_path, encoding="utf-8-sig")
                logging.info(f"📥 成功加载数据：{data_file_path}（共{len(df)}条）")
            except Exception as e:
                logging.error(f"❌ UTF-8编码读取数据失败（{data_file_path}）：{str(e)}")
                try:
                    df = pd.read_csv(data_file_path, encoding="latin1")
                    logging.info(f"📥 备用编码（latin1）加载数据成功：{data_file_path}")
                except Exception as e2:
                    logging.error(f"❌ 备用编码读取数据失败（{data_file_path}）：{str(e2)}")

        if os.path.exists(anno_file_path):
            try:
                with open(anno_file_path, "r", encoding="utf-8") as f:
                    annotations_data = json.load(f)
                for ann in annotations_data:
                    jama.append(set(ann.get("jama", [])))
                    gqs.append(int(ann.get("gqs", 1)))
                    discern.append(set(ann.get("discern", [])))
                    for col in meta.get("custom_columns", []):
                        col_name = col["name"]
                        col_type = col["type"]
                        if col_name not in custom_data:
                            custom_data[col_name] = []
                        value = ann.get(col_name, set() if col_type == "multi" else "")
                        if col_type == "multi" and isinstance(value, list):
                            value = set(value)
                        custom_data[col_name].append(value)
                logging.info(f"📥 成功加载注解数据：{anno_file_path}（共{len(annotations_data)}条）")
            except Exception as e:
                logging.error(f"❌ 加载注解数据失败（{anno_file_path}）：{str(e)}")
                jama = [set() for _ in range(len(df))]
                gqs = [1 for _ in range(len(df))]
                discern = [set() for _ in range(len(df))]
                for col in meta.get("custom_columns", []):
                    col_name = col["name"]
                    col_type = col["type"]
                    custom_data[col_name] = [set() if col_type == "multi" else "" for _ in range(len(df))]
        else:
            logging.warning(f"⚠️ 注解文件不存在：{anno_file_path}，初始化空注解")
            jama = [set() for _ in range(len(df))]
            gqs = [1 for _ in range(len(df))]
            discern = [set() for _ in range(len(df))]
            for col in meta.get("custom_columns", []):
                col_name = col["name"]
                col_type = col["type"]
                custom_data[col_name] = [set() if col_type == "multi" else "" for _ in range(len(df))]

        if len(df) > len(jama):
            jama.extend([set() for _ in range(len(df) - len(jama))])
            gqs.extend([1 for _ in range(len(df) - len(gqs))])
            discern.extend([set() for _ in range(len(df) - len(discern))])
            for col in meta.get("custom_columns", []):
                col_name = col["name"]
                col_type = col["type"]
                custom_data[col_name].extend([set() if col_type == "multi" else "" for _ in range(len(df) - len(custom_data[col_name]))])
            logging.info(f"📝 扩展注解长度以匹配数据：原注解{len(jama)-len(df)+len(jama)}条 → 新注解{len(jama)}条")

        return df, jama, gqs, discern, custom_data

    def add_history(self, filename, data, custom_columns):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        crawl_folder = os.path.join(self.history_dir, timestamp)
        os.makedirs(crawl_folder, exist_ok=True)
        logging.info(f"📁 创建新历史记录目录：{crawl_folder}")

        meta = {
            "timestamp": timestamp,
            "filename": filename,
            "count": len(data),
            "custom_columns": custom_columns
        }
        meta_file_path = os.path.join(crawl_folder, "meta.json")
        data_file_path = os.path.join(crawl_folder, "data.csv")
        anno_file_path = os.path.join(crawl_folder, "annotations.json")

        try:
            with open(meta_file_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            logging.info(f"📝 成功保存元数据：{meta_file_path}")
        except Exception as e:
            logging.error(f"❌ 保存元数据失败（{meta_file_path}）：{str(e)}")

        try:
            df = pd.DataFrame(data)
            expected_columns = [
                "title", "publish_time", "author_name", "like_count", "comment_count",
                "share_count", "collect_count", "video_url", "danmaku_count", "duration",
                "video_id", "play_count", "author_official_role", "is_verified"
            ]
            for col in expected_columns:
                if col not in df.columns:
                    if col in ["like_count", "comment_count", "share_count", "collect_count",
                               "danmaku_count", "play_count", "author_official_role"]:
                        df[col] = 0
                    else:
                        df[col] = ""
            df.to_csv(data_file_path, index=False, encoding="utf-8-sig")
            logging.info(f"📝 成功保存数据：{data_file_path}（共{len(df)}条，{len(df.columns)}个字段）")
        except Exception as e:
            logging.error(f"❌ 保存数据失败（{data_file_path}）：{str(e)}")

        empty_annotations = [
            {
                "jama": [],
                "gqs": 1,
                "discern": [],
                **{col["name"]: [] if col["type"] == "multi" else "" for col in custom_columns}
            }
            for _ in range(len(data))
        ]
        try:
            with open(anno_file_path, "w", encoding="utf-8") as f:
                json.dump(empty_annotations, f, ensure_ascii=False, indent=2)
            logging.info(f"📝 成功初始化空注解：{anno_file_path}（共{len(empty_annotations)}条）")
        except Exception as e:
            logging.error(f"❌ 初始化注解失败（{anno_file_path}）：{str(e)}")

        return meta

    def save_annotations(self, meta, jama, gqs, discern, custom_data):
        crawl_folder = os.path.join(self.history_dir, meta["timestamp"])
        anno_file_path = os.path.join(crawl_folder, "annotations.json")

        annotations = [
            {
                "jama": list(jama[i]),
                "gqs": gqs[i],
                "discern": list(discern[i]),
                **{col_name: list(custom_data[col_name][i]) if isinstance(custom_data[col_name][i], set) else custom_data[col_name][i] for col_name in custom_data}
            }
            for i in range(len(jama))
        ]

        try:
            with open(anno_file_path, "w", encoding="utf-8") as f:
                json.dump(annotations, f, ensure_ascii=False, indent=2)
            logging.info(f"📝 成功保存注解：{anno_file_path}（共{len(annotations)}条）")
        except Exception as e:
            logging.error(f"❌ 保存注解失败（{anno_file_path}）：{str(e)}")

    def save_custom_columns(self, meta, custom_columns):
        if not meta:
            return
        crawl_folder = os.path.join(self.history_dir, meta["timestamp"])
        meta_file_path = os.path.join(crawl_folder, "meta.json")
        try:
            with open(meta_file_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
            meta_data["custom_columns"] = custom_columns
            with open(meta_file_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
            logging.info(f"📝 成功保存自定义字段：{meta_file_path}")
        except Exception as e:
            logging.error(f"❌ 保存自定义字段失败（{meta_file_path}）：{str(e)}")

    def delete_history(self, meta):
        crawl_folder = os.path.join(self.history_dir, meta["timestamp"])
        if not os.path.exists(crawl_folder) or not os.path.isdir(crawl_folder):
            logging.warning(f"⚠️ 待删除的历史记录目录不存在：{crawl_folder}")
            return False
        try:
            import shutil
            shutil.rmtree(crawl_folder)
            logging.info(f"🗑️ 成功删除历史记录：{crawl_folder}（文件名：{meta['filename']}）")
            return True
        except Exception as e:
            logging.error(f"❌ 删除历史记录失败（{crawl_folder}）：{str(e)}")
            return False