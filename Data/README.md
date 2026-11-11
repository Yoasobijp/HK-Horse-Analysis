程式會從賽馬會排位頁尋找「所有賽事」PDF 連結，並在確認檔案有效後保存至 /DATA。
指定日期可用 python3 /home/ubuntu/download_hkjc_racecard.py --date 20261111；
若需覆寫已存在的檔案，請加上 --force。
