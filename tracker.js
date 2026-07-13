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

function generateThermalImage(data) {
    const width = 384; 
    const height = 190; // ফন্ট সাইজ ১ সাইজ কমানোয় হাইটও ১৯০ তে অপ্টিমাইজ করা হয়েছে
    const canvas = createCanvas(width, height);
    const ctx = canvas.getContext('2d');

    // প্লেইন হোয়াইট ব্যাকগ্রাউন্ড
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = '#000000'; // পিওর ব্ল্যাক ফন্ট
    ctx.textAlign = 'center';
    
    // ফন্ট সাইজ ২৮ এবং ইমেজের সাথে মিল রেখে sans-serif বোল্ড ব্যবহার করা হয়েছে
    ctx.font = 'bold 28px sans-serif'; 

    let currentY = 40; // প্রথম লাইনের শুরুর পজিশন

    data.goldData.forEach(item => {
        const name = nameMapping[item.n] || item.n;
        const gPrice = Number(item.bg_raw).toLocaleString('en-US', { maximumFractionDigits: 0 });

        // পুরো লাইনটি পেপারের মাঝখানে ইমেজের মতো সুন্দরভাবে বসে যাবে শেষে TK সহ
        ctx.fillText(`${name} ${gPrice} TK`, width / 2, currentY);
        
        currentY += 42; // প্রতি লাইনের মধ্যকার স্পেসিং
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
