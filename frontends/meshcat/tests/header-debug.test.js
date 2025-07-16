const WebSocket = require('ws');

describe('Header Debug Tests', () => {
  test('should test direct connection headers to understand what meshcat expects', async () => {
    console.log('📋 Testing direct connection to meshcat server...');
    
    // First test what works directly
    const directConnection = await new Promise((resolve) => {
      const ws = new WebSocket('ws://127.0.0.1:7000', {
        headers: {
          'User-Agent': 'Direct-Connection-Test'
        }
      });
      
      ws.on('open', () => {
        console.log('✅ Direct connection successful');
        ws.send('test');
      });
      
      ws.on('message', (data) => {
        const message = data.toString();
        console.log(`📋 Direct connection received: ${message.substring(0, 100)}...`);
        
        if (message.includes('Invalid Host/Origin header')) {
          console.log('❌ Direct connection also gets header error!');
          resolve({ success: false, headerError: true });
        } else {
          console.log('✅ Direct connection gets valid response');
          resolve({ success: true, headerError: false });
        }
        ws.close();
      });
      
      ws.on('close', (code) => {
        console.log(`📋 Direct connection closed: ${code}`);
        if (!resolve.called) {
          resolve({ success: code !== 1005, headerError: code === 1005 });
        }
      });
      
      ws.on('error', (error) => {
        console.log(`❌ Direct connection error: ${error.message}`);
        resolve({ success: false, error: error.message });
      });
      
      setTimeout(() => {
        ws.terminate();
        resolve({ success: false, error: 'timeout' });
      }, 5000);
    });

    // Now test with various header combinations
    const headerTests = [
      {
        name: 'No custom headers',
        headers: {}
      },
      {
        name: 'Localhost origin',
        headers: {
          'Origin': 'http://localhost:7000'
        }
      },
      {
        name: '127.0.0.1 origin',
        headers: {
          'Origin': 'http://127.0.0.1:7000'
        }
      },
      {
        name: 'Host and Origin set',
        headers: {
          'Host': '127.0.0.1:7000',
          'Origin': 'http://127.0.0.1:7000'
        }
      },
      {
        name: 'Null origin (some browsers)',
        headers: {
          'Origin': 'null'
        }
      }
    ];

    console.log('\n📋 Testing different header combinations:');
    
    for (const headerTest of headerTests) {
      console.log(`\n📋 Testing: ${headerTest.name}`);
      
      const result = await new Promise((resolve) => {
        const ws = new WebSocket('ws://127.0.0.1:7000', { headers: headerTest.headers });
        
        ws.on('open', () => {
          console.log(`✅ ${headerTest.name}: connection opened`);
          ws.send('test');
        });
        
        ws.on('message', (data) => {
          const message = data.toString();
          if (message.includes('Invalid Host/Origin header')) {
            console.log(`❌ ${headerTest.name}: gets header error`);
            resolve({ success: false, headerError: true });
          } else {
            console.log(`✅ ${headerTest.name}: gets valid response`);
            resolve({ success: true, headerError: false });
          }
          ws.close();
        });
        
        ws.on('close', (code) => {
          if (code === 1005) {
            console.log(`❌ ${headerTest.name}: closed with code 1005 (header rejection)`);
            resolve({ success: false, headerError: true });
          } else {
            resolve({ success: true, headerError: false });
          }
        });
        
        ws.on('error', (error) => {
          console.log(`❌ ${headerTest.name}: error - ${error.message}`);
          resolve({ success: false, error: error.message });
        });
        
        setTimeout(() => {
          ws.terminate();
          resolve({ success: false, error: 'timeout' });
        }, 3000);
      });

      if (result.success) {
        console.log(`🎉 SUCCESS: ${headerTest.name} works!`);
        console.log('📋 WORKING HEADERS:', headerTest.headers);
        break; // Found working combination
      }
    }

    expect(directConnection).toBeDefined();
  }, 30000);
});
