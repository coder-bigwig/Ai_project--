# JupyterHub 瀹炶骞冲彴锛圖ocker Compose 涓€閿儴缃诧級

鍩轰簬 Docker + JupyterHub 鐨勫绉熸埛鏁欏瀹炶骞冲彴锛屽寘鍚細

- **鍓嶇闂ㄦ埛**锛圧eact锛?
- **瀹為獙绠＄悊鍚庣**锛團astAPI锛孭ostgreSQL + Redis锛?
- **AI 鍔╂墜鏈嶅姟**锛團astAPI锛岄粯璁?DeepSeek锛屽彲閫?Tavily 鑱旂綉妫€绱級
- **JupyterHub**锛圖ockerSpawner锛氭瘡涓鐢熺嫭绔?Notebook 瀹瑰櫒锛?
- **鐩戞帶**锛圥rometheus + Grafana锛?
- **缁熶竴鍏ュ彛缃戝叧**锛圢ginx锛歚/` 鍓嶇銆乣/api` 鍚庣銆乣/jupyter` Hub锛?

> 缁熶竴鍏ュ彛锛堟湰鍦帮級锛歚http://localhost:8080`  
> 缁熶竴鍏ュ彛锛堟湇鍔″櫒锛夛細`http://<鏈嶅姟鍣↖P>/`  
> Hub 璺緞鍓嶇紑锛氶粯璁?`/jupyter`锛堝悓婧愬弽浠ｏ紝閫傚悎璇惧爞/鍐呯綉/鍏綉锛? 

---

## 1. 涓夌浣跨敤鏂瑰紡锛堝厛閫変竴涓級

| 鐩爣                         | 浣跨敤鏂瑰紡                            | 鍏ュ彛                    |
| ---------------------------- | ----------------------------------- | ----------------------- |
| 鏈湴瀹屾暣杩愯锛堟帹鑽愬厛璺戣繖涓級 | `docker-compose.yml` 鎴?`start.bat` | `http://localhost:8080` |
| 鍓嶇鐑洿鏂板紑鍙?              | `start-dev.bat`                     | `http://localhost:3000` |
| Linux 鏈嶅姟鍣ㄩ儴缃?            | `docker-compose.server.yml`         | `http://<鏈嶅姟鍣↖P>/`    |

---

## 2. 鐩綍缁撴瀯锛堟牳蹇冿級

```text
.
鈹溾攢鈹€ ai-service/                 # AI 鍔╂墜鏈嶅姟锛團astAPI锛?
鈹溾攢鈹€ backend/                    # 瀹為獙绠＄悊鍚庣锛團astAPI锛?
鈹溾攢鈹€ frontend/                   # 鍓嶇闂ㄦ埛锛圧eact锛?
鈹溾攢鈹€ experiments/                # 璇剧▼涓庡疄楠岃祫婧愶紙浼氬悓姝ュ埌 Docker 鍗凤級
鈹溾攢鈹€ jupyterhub/                 # JupyterHub 閰嶇疆锛圖ockerSpawner锛?
鈹溾攢鈹€ monitoring/                 # Prometheus / Grafana 閰嶇疆
鈹溾攢鈹€ nginx/                      # Nginx 閰嶇疆锛? /api /jupyter 鍙嶄唬锛?
鈹溾攢鈹€ docker-compose.yml          # 鏈湴瀹屾暣妯″紡
鈹溾攢鈹€ docker-compose.server.yml   # 鏈嶅姟鍣ㄩ儴缃叉ā寮?
鈹溾攢鈹€ start.bat                   # Windows 涓€閿惎鍔紙瀹屾暣妯″紡锛?
鈹溾攢鈹€ start-dev.bat               # Windows 寮€鍙戞ā寮忥紙鍓嶇鐑洿鏂帮級
鈹斺攢鈹€ stop-dev.bat                # 鍋滄寮€鍙戞ā寮忓悗绔鍣?
```

------

## 3. 鍓嶇疆瑕佹眰

- Docker Desktop锛圵indows/Mac锛夋垨 Docker Engine锛圠inux锛?
- Docker Compose锛坄docker compose` 鍙敤锛?
- Node.js 18+锛堜粎鈥滃紑鍙戞ā寮忊€濋渶瑕侊級

------

## 4. 鏈湴瀹屾暣妯″紡锛堟帹鑽愶級

### 4.1 Windows 涓€閿惎鍔?

鍦ㄤ粨搴撴牴鐩綍杩愯锛?

```bat
start.bat
```

鑴氭湰浼氭瀯寤洪暅鍍忓苟鍚姩瀹瑰櫒锛屽苟鍦?`experiment-manager` 瀹瑰櫒鍐呮墽琛?`python init_db.py` 鍒濆鍖栫ず渚嬪疄楠屾暟鎹€?

### 4.2 鎵嬪姩鍚姩锛堣法骞冲彴锛?

```bash
docker compose up -d --build
```

棣栨鍚姩寤鸿鎵ц涓€娆″垵濮嬪寲锛堝彲閲嶅鎵ц锛屽凡鏈夋暟鎹細璺宠繃锛夛細

```bash
docker compose exec -T experiment-manager python init_db.py
```

### 4.3 鏈湴璁块棶鍦板潃

- **缁熶竴鍏ュ彛锛堟帹鑽愶級**锛歚http://localhost:8080`
- **JupyterHub锛堢粡缃戝叧锛?*锛歚http://localhost:8080/jupyter/`
- 鍚庣 API 鏂囨。锛堢洿杩炲鍣ㄧ鍙ｏ級锛歚http://localhost:8001/docs`
- AI 鍔╂墜 API 鏂囨。锛歚http://localhost:8002/docs`
- JupyterHub锛堢洿杩炵鍙ｏ級锛歚http://localhost:8003`
- Grafana锛歚http://localhost:3001`锛堥粯璁?`admin/admin`锛?
- Prometheus锛歚http://localhost:9090`

### 4.4 鍋滄

```bash
docker compose down
```

------

## 5. 寮€鍙戞ā寮忥紙鍓嶇鐑洿鏂帮級

> 寮€鍙戞ā寮忎細锛氬惎鍔ㄥ悗绔浉鍏冲鍣紝骞?*鍋滄帀鐢熶骇鍓嶇/缃戝叧**锛岀劧鍚庡湪鏈満鍚姩 React dev server銆?

鍚姩锛?

```bat
start-dev.bat
```

鍋滄锛?

```bat
stop-dev.bat
```

鍙惎鍔ㄥ悗绔紙涓嶅惎鍔ㄥ墠绔?dev server锛夛細

```bat
set SKIP_FRONTEND=1 && start-dev.bat
```

寮€鍙戞ā寮忓叆鍙ｏ細

- 鍓嶇锛歚http://localhost:3000`
- 鍚庣 API锛歚http://localhost:8001`

鏇村璇存槑瑙?`DEV_MODE.md`銆?

------

## 6. 鏈嶅姟鍣ㄩ儴缃叉ā寮忥紙Linux锛?

蹇€熸楠わ細

```bash
cp .env.server.example .env
docker compose -f docker-compose.server.yml up -d --build
```

甯哥敤妫€鏌ワ細

```bash
docker compose -f docker-compose.server.yml ps
docker compose -f docker-compose.server.yml logs -f nginx
```

榛樿鍏ュ彛锛?

- 闂ㄦ埛锛歚http://<鏈嶅姟鍣↖P>/`
- JupyterHub锛歚http://<鏈嶅姟鍣↖P>/jupyter/`

璇︾粏璇存槑瑙?`DEPLOY_SERVER.md`銆?

------

## 7. 缃戝叧璺敱锛圢ginx锛?

骞冲彴閫氳繃 Nginx 鍋氱粺涓€鍏ュ彛锛?

- `/` 鈫?鍓嶇锛圧eact 闈欐€佺珯鐐癸級
- `/api/` 鈫?鍚庣锛坋xperiment-manager锛?
- `/jupyter/` 鈫?JupyterHub锛堟敮鎸?WebSocket锛屽唴鏍?缁堢/LSP 绛夛級

> 缃戝叧杩樻敮鎸佸皢 `?token=...` 鍐欏叆 Cookie锛屽苟妗ユ帴鍒?`Authorization`锛屾柟渚挎祻瑙堝櫒鍚屾簮璁块棶 JupyterHub銆?

------

## 8. 璐﹀彿涓庤璇佽鏄庯紙閲嶈锛?

### 8.1 闂ㄦ埛/鍚庣鐧诲綍

- 鐧诲綍鎺ュ彛锛歚POST /api/auth/login`
- 榛樿璐﹀彿鏉ユ簮锛堥€氳繃鐜鍙橀噺閰嶇疆锛夛細
  - 绠＄悊鍛橈細`ADMIN_ACCOUNTS`锛堥粯璁?`admin`锛?
  - 鏁欏笀锛歚TEACHER_ACCOUNTS`锛堥粯璁?`teacher_001` ~ `teacher_005`锛?
- 榛樿瀵嗙爜锛歚123456`锛堝缓璁娆＄櫥褰曞悗淇敼锛?

### 8.2 JupyterHub 鐧诲綍锛圖ummyAuthenticator锛?

- Hub 浣跨敤 `DummyAuthenticator`锛?
  - 鑻ユ湭璁剧疆 `DUMMY_PASSWORD`锛欻ub 鐧诲綍鍙娇鐢ㄤ换鎰忓瘑鐮侊紙**鍏綉涓嶅畨鍏?*锛?
  - 鍏綉閮ㄧ讲**鍔″繀璁剧疆** `DUMMY_PASSWORD`

------

## 9. 鍏抽敭鐜鍙橀噺

鎺ㄨ崘鍩轰簬 `.env.server.example` 閰嶇疆锛堟湇鍔″櫒妯″紡蹇呯敤锛涙湰鍦版ā寮忎篃鍙敤锛夛細

- `DB_PASSWORD`锛歅ostgreSQL 瀵嗙爜
- `EXPERIMENT_MANAGER_API_TOKEN`锛氬悗绔皟鐢?JupyterHub API 鐨勬湇鍔?token锛堝缓璁暱闅忔満涓诧級
- `DUMMY_PASSWORD`锛欽upyterHub 鍏变韩鐧诲綍鍙ｄ护锛堟湇鍔″櫒寮虹儓寤鸿璁剧疆锛?
- `JUPYTERHUB_BASE_URL`锛欻ub 璺緞鍓嶇紑锛堥粯璁?`/jupyter`锛?
- `JUPYTERHUB_PUBLIC_URL`锛氬悗绔繑鍥炵粰鍓嶇鐨?Hub 鍏綉鍦板潃锛堥粯璁?`/jupyter`锛?
- AI锛堝彲閫夛級锛?
  - `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`
  - `TAVILY_API_KEY`锛堣仈缃戞绱㈣兘鍔涳級
  - `CACHE_TTL` / `MAX_HISTORY`锛圓I 浼氳瘽缂撳瓨鍙傛暟锛?

------

## 10. 鏁版嵁涓庢寔涔呭寲锛堥噸瑕侊級

鏈」鐩粯璁や娇鐢?Docker volumes 鍋氭寔涔呭寲锛堥噸鍚?鍗囩骇涓嶄涪鏁版嵁锛夛細

- `postgres-data`：PostgreSQL 数据
- `redis-data`：Redis 数据
- `jupyterhub-data`：JupyterHub 配置/密钥/运行状态
- 后端上传文件（资源/附件/提交 PDF）统一存储到 PostgreSQL（`BYTEA`）
- `course-materials`：课程与实验资源（由 `data-loader` 从 `./experiments` 同步）

> 鍚庣瀛樺偍鍚庣 **鍙厑璁?PostgreSQL**锛堜笉浼氬洖閫€鍒?JSON锛夈€傚鏋?Postgres 鍒濆鍖栧け璐ワ紝鍚庣浼氱洿鎺ラ€€鍑猴紝閬垮厤鈥滅湅浼艰兘璺戜絾娌¤惤搴撯€濈殑鎯呭喌銆?

历史文件迁移到 PG（一次性）：
```bash
cd backend
python -m app.scripts.migrate_file_blobs_to_pg
# 如需迁移后删除旧磁盘文件：
python -m app.scripts.migrate_file_blobs_to_pg --delete-source
```

------

## 11. 甯哥敤鍛戒护

鏈湴瀹屾暣妯″紡锛?

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f experiment-manager
docker compose down
```

鏈嶅姟鍣ㄦā寮忥細

```bash
docker compose -f docker-compose.server.yml up -d --build
docker compose -f docker-compose.server.yml ps
docker compose -f docker-compose.server.yml logs -f nginx
docker compose -f docker-compose.server.yml down
```

鍒濆鍖栫ず渚嬪疄楠屾暟鎹細

```bash
docker compose exec -T experiment-manager python init_db.py
```

------

## 12. 甯歌闂锛團AQ锛?

### 12.1 绔彛鍐茬獊

鏈湴瀹屾暣妯″紡鑷冲皯闇€瑕佽繖浜涚鍙ｅ彲鐢細`8080`銆乣8001`銆乣8002`銆乣8003`銆乣3001`銆乣9090`銆?
寮€鍙戞ā寮忚繕闇€瑕?`3000`銆?

### 12.2 璁块棶 `/jupyter` 鐧藉睆鎴栧唴鏍告棤娉曡繛鎺?

- 纭繚浣犳槸璧扮綉鍏筹細`http://localhost:8080/jupyter/`锛堣€屼笉鏄洿鎺?`8003`锛?
- 纭繚 Nginx 閰嶇疆閲?WebSocket 鍙嶄唬鍚敤锛堟湰浠撳簱宸查厤缃級

### 12.3 鏈嶅姟鍣ㄤ笂涓轰粈涔?AI/鐩戞帶榛樿鎵撲笉寮€锛?

鏈嶅姟鍣?compose 榛樿鎶?AI / Prometheus / Grafana 绔彛缁戝畾鍒?`127.0.0.1`锛岄€傚悎閫氳繃 SSH 闅ч亾璁块棶锛堟洿瀹夊叏锛夈€傚闇€鍏綉寮€鏀撅紝璇蜂慨鏀?`docker-compose.server.yml` 鐨勭鍙ｇ粦瀹氥€?

------

## 13. 鎶€鏈爤

- Frontend: React + axios + react-router-dom
- Backend: FastAPI + SQLAlchemy + Alembic + asyncpg/psycopg2 + Redis
- Hub: JupyterHub + DockerSpawner
- Proxy: Nginx
- Observability: Prometheus + Grafana
- AI: DeepSeek Chat Completions锛堝彲閫?Tavily web search锛?
