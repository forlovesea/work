##0, 1, 1, 2, 3, 5, 8, 13...
#       
#num = [0, 1]
#
#while 1:
#    user = input("피보나치 수열  프린트: 숫자를 입력해 주세요:")
#    print("입력된 값: " + user)
#    if user.isdigit() :
#        break
#
#user = int(user)
#a = 0
#p = ""
#while 1:
#    if a == 0:
#        b = a + 1
#        if b < user:            
#            p = str(a) + "," + str(b)            
#        else:
#            break
#        
#        c = a + b        
#        if c < user:        
#            p = p + "," + str(c)            
#        else:            
#            break
#        a = 1
#    
#    b = b + c
#    c = b + c
#    if b < user:
#        p = p + "," + str(b)
#    else:
#        break
#    if c < user:
#        p = p + "," + str(c)
#    else:
#        break
#print(p)

def fib(n):
    if n == 0 : return 0
    if n == 1 : return 1
    return fib(n-2) + fib(n-1)

for i in range(10):
    print(fib(i))


user = input("숫자 입력:")    
list = user.split(",")
print(list)
a = 0
while list:
    a = a + int(list.pop())

print("합산:" + str(a))
    

