const { defineConfig } = require('@playwright/test');
module.exports=defineConfig({testDir:'./browser-tests',workers:1,timeout:30000,
  use:{baseURL:'http://127.0.0.1:8765',browserName:'chromium',locale:'en-US',timezoneId:'UTC',colorScheme:'light',viewport:{width:1440,height:900}},
  webServer:{command:'PYTHONPATH=src python3 -m qc_pipeline.review_server --ephemeral',url:'http://127.0.0.1:8765/api/cases',reuseExistingServer:false}});
