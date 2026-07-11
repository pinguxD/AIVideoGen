from radar.gameplay_miner import mine_raw_gameplay

if __name__ == '__main__':
    hits = mine_raw_gameplay(force=False)
    print(f'Done. Mined/registered {len(hits)} clips into assets/source/mined/')
