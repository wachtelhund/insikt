// ClawHub weather skill. Reaches api.open-meteo.com, which is not on the default
// allowlist, so Insikt should raise an egress finding (but no exfil triad — it
// neither runs shell nor reads credentials).
async function forecast(lat, lon) {
  const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m`);
  return res.json();
}
module.exports = { forecast };
