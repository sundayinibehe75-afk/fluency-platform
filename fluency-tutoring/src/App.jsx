import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { NotificationProvider } from './context/NotificationContext'
import Home from './pages/Home'
import Register from './pages/auth/Register'
import Login from './pages/auth/Login'
import ResetPassword from './pages/auth/ResetPassword'
import TutorProfile from './pages/tutor/TutorProfile'
import BookingCalendar from './pages/booking/BookingCalendar'
import BookingSuccess from './pages/booking/BookingSuccess'
import BookingCancelled from './pages/booking/BookingCancelled'
import LessonRoom from './pages/lesson/LessonRoom'
import StudentDashboard from './pages/dashboard/StudentDashboard'
import AdminDashboard from './pages/dashboard/AdminDashboard'
import Inbox from './pages/messages/Inbox'
import ReviewForm from './pages/reviews/ReviewForm'

export default function App() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/register" element={<Register />} />
          <Route path="/login" element={<Login />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/tutor/:id" element={<TutorProfile />} />
          <Route path="/booking" element={<BookingCalendar />} />
          <Route path="/booking/success" element={<BookingSuccess />} />
          <Route path="/booking/cancelled" element={<BookingCancelled />} />
          <Route path="/lessons/:id" element={<LessonRoom />} />
          <Route path="/dashboard" element={<StudentDashboard />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/messages" element={<Inbox />} />
          <Route path="/reviews/:bookingId" element={<ReviewForm />} />
        </Routes>
      </NotificationProvider>
    </AuthProvider>
  )
}
