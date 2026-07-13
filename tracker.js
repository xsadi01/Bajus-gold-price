const fs = require('fs');
const path = require('path');
const fetch = require('node-fetch');
const { createCanvas } = require('canvas');

const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;
const GITHUB_REPOSITORY = process.env.GITHUB_REPOSITORY || "xsadi01/Bajus-gold-price"; 

const LAST_PRICE_FILE = path.join(__dirname, 'last_price.json');
const IMAGE_OUTPUT_FILE = path.join(__dirname, 'thermal_print.png');
const TARGET_URL = 'https://www.goldr.org/price.js?gttm';

// ইমেজ অনুযায়ী নামগুলো ছোট (Short) করা হলো
const nameMapping = {
    "২২ ক্যারেট সোনার দাম": "22K-",
    "২১ ক্যারেট সোনার দাম": "21K-",
    "১৮ ক্যারেট সোনার দাম": "18K-",
    "সনাতন পদ্ধতির সোনার দাম": "SAN-"
};

async function getLatestMarketData() {
    try {
        const response = await fetch(TARGET_URL, { headers: { 'User-Agent': 'Mozilla/5.0' } });
        const jsContent = await response.text();
        const goldMatch = jsContent.match(/GoldrPriceTable_goldData\s*=\s*(\[[\s\S]*?\]);/);
        const dateMatch = jsContent.match(/const datetime\s*=\s*"([^"]+)"/);

        if (!goldMatch) throw new Error("Format not found");

        const goldData = JSON.parse(goldMatch[1]);
        let updateDate = new Date().toISOString().split('T')[0];
        if (dateMatch && dateMatch[1]) updateDate = dateMatch[1].split(' ')[0];

        return { goldData, updateDate };
    } catch (error) {
        console.error("Data error:", error.message);
        return null;
    }
}

// ইমেজ সাইজ ও ফন্ট রেশিও হুবহু সেম রেখে ব্ল্যাক অ্যান্ড হোয়াইট করার ফাংশন
function generateThermalImage(data) {
    // থার্মাল প্রিন্টারের ফুল পেপার সাইজ (যাতে সাইডে কোনো ফাঁকা না থাকে)
    const width = 384; 
    const height = 256; // আপনার ইমেজের হাইট-উইডথ অনুপাত (1000x667) অনুযায়ী পারফেক্ট স্কেলিং
    
    const canvas = createCanvas(width, height);
    const ctx = canvas.getContext('2d');

    // প্লেইন হোয়াইট ব্যাকগ্রাউন্ড
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = '#000000'; // পিওর ব্ল্যাক কালার
    
    // আপনার ইমেজের মতো বিশাল বোল্ড ফন্ট (৩৮৪ উইডথ এর জন্য ৪৪px একদম ফুল সাইড কভার করবে)
    ctx.font = 'bold 44px Arial, sans-serif'; 

    let currentY = 52; // শুরুর ওয়াই পজিশন

    data.goldData.forEach(item => {
        const name = nameMapping[item.n] || item.n;
        const gPrice = Number(item.bg_raw).toLocaleString('en-US', { maximumFractionDigits: 0 });

        // বাম পাশে নাম (22K-)
        ctx.textAlign = 'left';
        ctx.fillText(name, 10, currentY);

        // ডান পাশে প্রাইস এবং শেষে TK
        ctx.textAlign = 'right';
        ctx.fillText(`${gPrice} TK`, width - 10, currentY);
        
        currentY += 62; // আপনার ইমেজের মতো লাইন টু লাইন বড় গ্যাপ (Row Spacing)
    });

    const buffer = canvas.toBuffer('image/png');
    fs.writeFileSync(IMAGE_OUTPUT_FILE, buffer);
    console.log("Image style updated perfectly.");
}

async function sendTelegramNotification(message, imageUrl) {
    if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
        console.log("Telegram tokens missing. Skipping message send.");
        return;
    }

    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
    const replyMarkup = {
        inline_keyboard: [[
            { text: "Download", url: imageUrl }
        ]]
    };

    try {
        await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: TELEGRAM_CHAT_ID,
                text: message,
                parse_mode: 'Markdown',
                reply_markup: replyMarkup
            })
        });
        console.log("Notification sent.");
    } catch (error) {
        console.error("Telegram error:", error);
    }
}

async function run() {
    const currentData = await getLatestMarketData();
    if (!currentData) return;

    generateThermalImage(currentData);

    let oldData = null;
    if (fs.existsSync(LAST_PRICE_FILE)) {
        try { oldData = JSON.parse(fs.readFileSync(LAST_PRICE_FILE, 'utf8')); } catch (e) { oldData = null; }
    }

    if (oldData && JSON.stringify(currentData.goldData) === JSON.stringify(oldData.goldData)) {
        console.log("No price change detected. Image updated but skipping telegram alert.");
        return;
    }

    let message = `🔔 *GOLD PRICE UPDATED*\n`;
    message += `📅 \`${currentData.updateDate}\`\n\n`;
    message += `\`Type   | Per Gram | Per Vori \`\n`;
    message += `\`-------------------------------\`\n`;
    
    currentData.goldData.forEach(item => {
        const name = nameMapping[item.n] || item.n;
        const cleanName = name.replace('-', '').padEnd(6, ' ');
        const gPrice = Number(item.bg_raw).toLocaleString('en-US', { maximumFractionDigits: 0 }).padEnd(6, ' ');
        const vPrice = Number(item.bv_raw).toLocaleString('en-US', { maximumFractionDigits: 0 }).padEnd(6, ' ');
        message += `\`${cleanName} | ${gPrice} | ${vPrice} ৳\`\n`;
    });

    const rawImageUrl = `https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/main/thermal_print.png?t=${Date.now()}`;

    await sendTelegramNotification(message, rawImageUrl);

    fs.writeFileSync(LAST_PRICE_FILE, JSON.stringify(currentData, null, 2), 'utf8');
}

run();
