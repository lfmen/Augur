document.addEventListener('DOMContentLoaded', async () => {
    
    // Circle Progress logic
    const circle = document.querySelector('.progress-ring__circle');
    const radius = circle.r.baseVal.value;
    const circumference = radius * 2 * Math.PI;
    
    circle.style.strokeDasharray = `${circumference} ${circumference}`;
    circle.style.strokeDashoffset = circumference;

    function setProgress(percent) {
        const offset = circumference - percent / 100 * circumference;
        circle.style.strokeDashoffset = offset;
        
        // Dynamically change color based on viability
        if(percent >= 65) {
            circle.style.stroke = 'var(--green)';
        } else if(percent >= 40) {
            circle.style.stroke = 'var(--yellow)';
        } else {
            circle.style.stroke = 'var(--red)';
        }
    }

    try {
        const cacheBuster = new Date().getTime();
        const response = await fetch(`data.json?t=${cacheBuster}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Update Timestamp
        document.getElementById('update-date').textContent = data.timestamp;
        
        // Score & Progress Ring
        const scorePct = data.viability_score * 100;
        
        // Animate counter
        let currentScore = 0;
        const targetScore = parseFloat(scorePct.toFixed(1));
        const duration = 2000;
        const steps = 60;
        const increment = targetScore / steps;
        
        const counterInterval = setInterval(() => {
            currentScore += increment;
            if(currentScore >= targetScore) {
                currentScore = targetScore;
                clearInterval(counterInterval);
            }
            document.getElementById('viability-score').textContent = `${currentScore.toFixed(1)}%`;
        }, duration / steps);

        // Animate Ring
        setTimeout(() => setProgress(targetScore), 100);
        
        // Opinion Text Split into Title and Body
        if (data.opinion) {
            const cleanOpinion = data.opinion.replace(/\*\*/g, '').trim();
            const firstPeriodIndex = cleanOpinion.indexOf('.');
            
            if (firstPeriodIndex !== -1) {
                const title = cleanOpinion.substring(0, firstPeriodIndex).trim();
                const body = cleanOpinion.substring(firstPeriodIndex + 1).trim();
                document.getElementById('opinion-title').textContent = title;
                document.getElementById('opinion-text').textContent = body;
            } else {
                document.getElementById('opinion-title').textContent = 'Análisis de Viabilidad';
                document.getElementById('opinion-text').textContent = cleanOpinion;
            }
        }

        // ICG & ICC
        const icg = data.variables.ICG_Aprobacion;
        document.getElementById('icg-value').textContent = icg != null ? icg.toFixed(2) : '--';
        if(icg != null) {
            setTimeout(() => {
                document.getElementById('icg-meter').style.width = `${Math.min((icg / 3.5) * 100, 100)}%`;
            }, 500);
        }

        const icc = data.variables.ICC_Nivel;
        document.getElementById('icc-value').textContent = icc != null ? icc.toFixed(1) : '--';
        if(icc != null) {
            setTimeout(() => {
                document.getElementById('icc-meter').style.width = `${Math.min((icc / 60) * 100, 100)}%`;
            }, 500);
        }

        // Indicators formatter
        const formatIndicator = (val, suffix="", isDelta=false) => {
            if (val == null) return '--';
            const prefix = (isDelta && val > 0) ? '+' : '';
            return `${prefix}${val}${suffix}`;
        };

        const formatCurrency = (val) => {
            if (val == null) return '--';
            return `$${val.toLocaleString('es-AR', {maximumFractionDigits: 0})}`;
        };

        // Populate Cards
        document.getElementById('ipc-value').textContent = formatIndicator(data.variables.IPC_BCRA?.toFixed(1), '%');
        document.getElementById('acel-value').textContent = formatIndicator(data.variables.IPC_Delta_1M?.toFixed(1), '', true);
        document.getElementById('brecha-value').textContent = formatIndicator(data.variables.Brecha_Cambiaria?.toFixed(1), '%');
        document.getElementById('salario-value').textContent = formatIndicator(data.variables.Salario_Delta_1M?.toFixed(2), '%', true);
        document.getElementById('empleo-value').textContent = formatIndicator(data.variables.Empleo_Delta_1M?.toFixed(2), '%', true);
        document.getElementById('emae-value').textContent = formatIndicator(data.variables.EMAE_Delta_1M?.toFixed(1), '%', true);
        
        const fiscal = data.variables.Resultado_Financiero_Millones;
        document.getElementById('fiscal-value').textContent = fiscal != null ? `${formatCurrency(fiscal/1000)} B` : '--';
        
        const rin = data.variables.RIN_Est_USD;
        document.getElementById('rin-value').textContent = rin != null ? `USD ${rin.toLocaleString('es-AR')} M` : '--';

        // Add colors to deltas
        ['acel-value', 'salario-value', 'empleo-value', 'emae-value', 'fiscal-value'].forEach(id => {
            const el = document.getElementById(id);
            if(el && el.textContent !== '--') {
                const valStr = el.textContent.replace(/[^\d.-]/g, '');
                const val = parseFloat(valStr);
                
                // Specific logic for inflation vs others
                let isGood = val > 0;
                if(id === 'acel-value') isGood = val < 0; // Acceleration < 0 is good
                
                if (isGood) el.classList.add('color-green');
                else if (val < 0 || (id === 'acel-value' && val > 0)) el.classList.add('color-red');
            }
        });

    } catch (error) {
        console.error('Error fetching data:', error);
        document.getElementById('update-date').textContent = 'Error al cargar datos. Asegúrate de que data.json existe.';
    }
});
