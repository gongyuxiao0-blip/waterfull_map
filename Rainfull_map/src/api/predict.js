import axios from "axios"

export function getRainPredict(targetType, targetName, days = 1) {
  return axios.get("http://127.0.0.1:5000/api/predict/rain", {
    params: {
      target_type: targetType,
      target_name: targetName,
      days
    }
  })
}