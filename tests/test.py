import asyncio
from gemini_webapi.constants import Model
from gemini_webapi import GeminiClient
# Replace "COOKIE VALUE HERE" with your actual cookie values.
# Leave Secure_1PSIDTS empty if it's not available for your account.
Secure_1PSID = "g.a0009Qhc9m50gxp6J-6qIOtuHhC_QOnVmfqxIhUj589p4f6fl2yspvkK9QtApqM7_47pfu0_sQACgYKAXISARcSFQHGX2Mi-3AcT6n25NYycx2KucoxLxoVAUF8yKr4vsG9Mre7sXv2J1bCV4py0076"
Secure_1PSIDTS = "sidts-CjcBhkeRd35dsw-B8exd8-mP9lejgU9QrnBt7vqJHHHUdIQCrjWFgUzcEOPof_QuufH57BKduycjEAA"
proxy = 'http://127.0.0.1:7897'
async def main():
    # If browser-cookie3 is installed, simply use `client = GeminiClient()`
    client = GeminiClient(Secure_1PSID, Secure_1PSIDTS, proxy=proxy)
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    response = await client.generate_content("我目前gemini ai 的权益？")
    print(response.text)
asyncio.run(main())

"""

HSID=A3jMBF5g1fbfoGgtD; SSID=AgOxVBRHctvRcz_hf;
 APISID=yNfHf0GKHXJzBYX5/AikkkkduSjDyLFK8x; 
 SAPISID=KyuG_ExtVpJ9I7YV/A2-WQ68wj0TDkNhYB;
  __Secure-1PAPISID=KyuG_ExtVpJ9I7YV/A2-WQ68wj0TDkNhYB;
   __Secure-3PAPISID=KyuG_ExtVpJ9I7YV/A2-WQ68wj0TDkNhYB; 
   SID=g.a0009Qhc9m50gxp6J-6qIOtuHhC_QOnVmfqxIhUj589p4f6fl2ysna3ia35Sdq3fOBMchUG9BAACgYKASISARcSFQHGX2MiqwqzbqxKefZcYTIMMulkZxoVAUF8yKr3nBX3ADtjHSK4YjKySCAV0076; 
   __Secure-1PSID=g.a0009Qhc9m50gxp6J-6qIOtuHhC_QOnVmfqxIhUj589p4f6fl2yspvkK9QtApqM7_47pfu0_sQACgYKAXISARcSFQHGX2Mi-3AcT6n25NYycx2KucoxLxoVAUF8yKr4vsG9Mre7sXv2J1bCV4py0076; 
   __Secure-3PSID=g.a0009Qhc9m50gxp6J-6qIOtuHhC_QOnVmfqxIhUj589p4f6fl2ysVoDTB_UD6v5MF7iMrFuKlgACgYKAUQSARcSFQHGX2MiP5FeWU9hrkWigbZJX21B2BoVAUF8yKpjMaYIfa4SA2V35Z5eYpnj0076; 
   SEARCH_SAMESITE=CgQI26AB; 
   __Secure-BUCKET=CJoH; _gcl_au=1.1.379108103.1777345420;
    _ga=GA1.1.340823058.1777345434; 
    AEC=AaJma5sT-wuv2Y-WpCNZs56a2ZHvPt4QV7_RwQ3eTrfNxjbHbzswMW50GcM; 
    COMPASS=gemini-pd=CjwACWuJV93jFYb_b6k1ZbZc5AVi75OXfwVJx6huPFdJgLZgT-iphNSBtyIyTho-2Gurv4U86El7hPmdVFUQx8CW0AYaaAAJa4lXFtX2GRtlJC7uJxUwbQSbjXy_4ln5DdT8l55DRTqrOgY9D-el2cxaL_pSnxNHdmdi_pEhZTxWwsbxadU6YFW8VefTBcTuf4bAQyeUGhjEkPYj6x06SVTMftRp58hSeasGGkUgIAEwAQ:gemini-hl=CkkACWuJV4Jq7gXnYGXm-CCWRGf1MNczIJ0yMsen8R98zb0fdd_v1HDcw_-Y0Gxw7WZu_GGVl89NUAGecp6EG6tM_DjudIlkdiK-EP7RldAGGnUACWuJVxVDUIEGKtXR12wZ-Bm5WiBeQ1Q_b_ty45qSS3jfohIpTRohCauwfJjtpcDyFup9g5kYCHfL9pgu0Qas940lAF_r_qYKkQB-hre_qnma_0ONzOTIucksqO_EteBkBvAqZnJ0TCNuHr3o0CpenQFlnZUgATAB; _ga_BF8Q35BMLM=GS2.1.s1778677582$o5$g1$t1778677643$j60$l0$h0; 
    _ga_WC57KJ50ZZ=GS2.1.s1778677582$o6$g1$t1778677647$j56$l0$h0; 
    NID=531=DpUSHIZNAzjxB7uCGfiwl6qUD_Vzfb0jRP8SiZLTyHy-1KEcJEbhOQHdQdBvl_ClzfUMkgAQdRUCIlMIVBZEUhhpH3pt4xUGvQCyd2m5q66Y_-yS8p1CbiBIWdyHM7YV3eMzHUjnAYdd26P6oNjFXHS1sI5pZBGOzZ4uThiG62Evvx3YT7l8Nymf5myqFmZY_KT6-AMR2hBLOO1hb3DFIuLWZ1-bXujSBBdxBDcufCRG_4MuClYx0j-E8f1KmxR0aHbYnCOU1G7ADNYV4o5_IZ84GHA7ttAA0M5CYI_n-XMlbBLZ05PrVdHpUfeVPw2PuTD8T6gkCzEEVN8GMNGW2pBWwpuPyscZwDJ0Q7M6wndowKil9DLXMJFcCgO-sppkJOP5E16SJCFJF5VotNrnMZUYwE9Bh-7YNauUvBD0HLkXDEda1orR_u_4Sb7AlDVilZYrZxTgOKfYU90JWCoNwJ3cHehfCRAZOTn6pHuE1XyKDDCxQQfz-bAAuIsl5bl0Icz9AralM5eJEAxz2b7RH_qGz-uIxOa4ca3uKyJFpe_nAw77W5MA2paMgqtwdXhLANLk_kMip2iFLjqe7LIiLUFALonbgMHwK6h1QCNRCKazy-GpJEx99ijRNZj70LHH-zil87wkY-KJ4m-15OeQ1ZCBezeN6Byl0vmcyfF9KnrGUNBi7sxxYDhfhZFirjEvjt1PvWzQGVbfxbHjcQRUSQ; 
    __Secure-1PSIDTS=sidts-CjcBhkeRd35dsw-B8exd8-mP9lejgU9QrnBt7vqJHHHUdIQCrjWFgUzcEOPof_QuufH57BKduycjEAA;
      __Secure-1PSIDRTS=sidts-CjcBhkeRd35dsw-B8exd8-mP9lejgU9QrnBt7vqJHHHUdIQCrjWFgUzcEOPof_QuufH57BKduycjEAA; 
       __Secure-3PSIDTS=sidts-CjcBhkeRd35dsw-B8exd8-mP9lejgU9QrnBt7vqJHHHUdIQCrjWFgUzcEOPof_QuufH57BKduycjEAA; __Secure-3PSIDRTS=sidts-CjcBhkeRd35dsw-B8exd8-mP9lejgU9QrnBt7vqJHHHUdIQCrjWFgUzcEOPof_QuufH57BKduycjEAA; 
    SIDCC=AKEyXzW31wzc_r6w3c5BYhrYawZjvLx7RvOXR48Gn0w-7ZhOX_EVVDSBoyOxJo4jlp4_4sOR0A; 
    
    __Secure-1PSIDCC=AKEyXzUQWtdryscU-kfziydj0NR626JKrsCj3Vg1YKXbANjbOEwrM9Gar3rn0JIYHmaBN2VVkg; 
    __Secure-3PSIDCC=AKEyXzWYbX2vSVoA6nm_IrL43H0fGM2XNPb1fGl2fiKJjuHybHz5gneUMY-Rjh0Cye2lx3mx_Q
"""