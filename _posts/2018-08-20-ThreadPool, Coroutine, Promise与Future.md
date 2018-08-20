---
layout: post
title: "ThreadPool, Coroutine, Promise与Future"
---
# ThreadPool, Coroutine, Promise与Future

## ThreadPool
线程池，顾名思义，就是放着很多线程的大“池子”。主要用作并发量大，但每个任务需要处理的时间不是很长。比如接受或者发送网络请求的任务。之所以使用线程池，原因就是在线程的传创建和销毁在高并发先开销十分大，如果将线程先创建好放入“池子”中待命，随用随取。降低不必要的开销十分划算。

实现也非常的简单，创建队列，使用生产消费者模型（向队列中增加任务即生产者，将任务执行完成即消费者）。主要实现逻辑如下：

```c++
ThreadPool::ThreadPool(int thread_size) 
{
    is_stop = false;
    thread_size_ = thread_size;
    pthread_mutex_init(&mutex_, NULL);
    pthread_cond_init(&empty_cond_, NULL);
    for(int i = thread_size_; i > 0; i--) {
        thread *t = new thread([=](){
            while(true){
                pthread_mutex_lock(&mutex_);
                while(task_list_.empty() && !is_stop) {
                    pthread_cond_wait(&empty_cond_, &mutex_);
                }
                if (is_stop) {
                    pthread_mutex_unlock(&mutex_);
                    return;
                }
                Task task = task_list_.front();
                task_list_.pop();
                pthread_mutex_unlock(&mutex_);
                
                task.f(task.arg);
            }
        });
        thread_vec_.push_back(move(t));
    }
}

```
## Coroutine
协程，又称微线程。这个也名字起的也是很通俗易懂的。就是比线程规模还要小的调度单位。主要用在多并发且I/O开销较高的场景，并且能够减少callback逻辑的使用。在某些不需要并行要求不高的场景下，减少了锁的使用。

在操作系统中，最小的调度单位就已经是线程了。协程其实就是用户态的线程，即何时调度怎样调度由用户自己控制，而不是由系统控制。操作系统分配给用户一个时间片，用户又将这个时间片再次拆分，更加精细的规划利用。由于用户自己拆分利用，开销就要比系统调度的线程小，操作系统不需要在用户与内核态之间切换，不用更换页表。试想在一个高并发多I/O的任务中，线程遇到的I/O阻塞，被切换调度，另个一线程运行一会也阻塞，这样系统需要维护很多线程，很吃系统的资源。但是在协程中，一旦协程任务遇到了I/O，切换到另一个协程任务，开销只是切换了寄存器和栈，而且还是用户态下的。系统在维护少量线程的情况下能够执行更多的任务，将计算资源高效利用。而且调度是由用户控制，大多数情况下在并发下引起的竞争就不存在了，也就减少了锁的使用。

协程的实现要比线程池要麻烦一些，主要是因为用户需要在切换时需要自己保存每个任务的状态。在*nix下系统提供了ucontext库，将任务切换时寄存器与栈的切换封装好的。实现的核心如下列代码所示:

```c++

CoroutineBase::CoroutineBase(ucontext_t* main_ctx, void* arg):
		status_(CorStatus::suspend), stack_ptr_(NULL), main_ctx_(main_ctx),
		arg_(arg), yeild_(NULL)
{
	if (main_ctx_ == NULL) return;
	stack_ptr_ = new char[1024 * 32];
	getcontext(&ctx_);
	ctx_.uc_stack.ss_sp = stack_ptr_;
	ctx_.uc_stack.ss_size = 1024 * 32;
	ctx_.uc_stack.ss_flags = 0;
	ctx_.uc_link = main_ctx;
	makecontext(&ctx_, (void (*) (void)) &CoroutineBase::WrapperFunc, 2, this, arg_);
}

void* CoroutineBase::Yeild(void * yeild) {
	if (yeild != NULL) yeild = yeild_;
	status_ = CorStatus::suspend;
	swapcontext(&ctx_, main_ctx_);
	status_ = CorStatus::running;
	return yeild_;
}

```


```c++

CoroutineMain::CoroutineMain() {
	stack_ptr_ = new char[1024 * 32];
	getcontext(&ctx_main_);
	ctx_main_.uc_stack.ss_sp = stack_ptr_;
	ctx_main_.uc_stack.ss_size = 1024 * 32;
	ctx_main_.uc_stack.ss_flags = 0;
	makecontext(&ctx_main_, (void (*) (void)) &CoroutineMain::Run, 1, this);
}
void CoroutineMain::Run() {
	static int x = 8;
	auto list_it = list_ctx_.begin();
	while(!list_ctx_.empty()) {
		if ((*list_it)->get_status() == CorStatus::stop) {
			list_it = list_ctx_.erase(list_it);
		} else if ((*list_it)->get_status() == CorStatus::suspend) {
			ucontext_t* ctx = &(*list_it)->ctx_;
			(*list_it)->yeild_ = (void *)&x;
			swapcontext(&ctx_main_, ctx);
			list_it++;
			if (list_it == list_ctx_.end()) list_it = list_ctx_.begin();
		}
	}
}
void CoroutineMain::CreateCoroutine(CoroutineBase *cor) {
	if (cor != NULL) list_ctx_.push_back(cor);
}

```
在实现中我模仿python的yield，在协程中可以传入穿出参数。调试反编译swap可以看到其过程其实就是将现有协程的寄存器的信息保存（保留其上下文），在把要切换的寄存器信息恢复，跟操作系统进程间切换是很相似的。

```asm
(gdb) disassemble
Dump of assembler code for function swapcontext:
=> 0x00007ffff753e400 <+0>:	mov    %rbx,0x80(%rdi)
   0x00007ffff753e407 <+7>:	mov    %rbp,0x78(%rdi)
   0x00007ffff753e40b <+11>:	mov    %r12,0x48(%rdi)
   0x00007ffff753e40f <+15>:	mov    %r13,0x50(%rdi)
   0x00007ffff753e413 <+19>:	mov    %r14,0x58(%rdi)
   0x00007ffff753e417 <+23>:	mov    %r15,0x60(%rdi)
   0x00007ffff753e41b <+27>:	mov    %rdi,0x68(%rdi)
   0x00007ffff753e41f <+31>:	mov    %rsi,0x70(%rdi)
   0x00007ffff753e423 <+35>:	mov    %rdx,0x88(%rdi)
   0x00007ffff753e42a <+42>:	mov    %rcx,0x98(%rdi)
   0x00007ffff753e431 <+49>:	mov    %r8,0x28(%rdi)
   0x00007ffff753e435 <+53>:	mov    %r9,0x30(%rdi)
   0x00007ffff753e439 <+57>:	mov    (%rsp),%rcx
   0x00007ffff753e43d <+61>:	mov    %rcx,0xa8(%rdi)
   0x00007ffff753e444 <+68>:	lea    0x8(%rsp),%rcx
   0x00007ffff753e449 <+73>:	mov    %rcx,0xa0(%rdi)
   0x00007ffff753e450 <+80>:	lea    0x1a8(%rdi),%rcx
   0x00007ffff753e457 <+87>:	mov    %rcx,0xe0(%rdi)
   0x00007ffff753e45e <+94>:	fnstenv (%rcx)
   0x00007ffff753e460 <+96>:	stmxcsr 0x1c0(%rdi)
   0x00007ffff753e467 <+103>:	mov    %rsi,%r12
   0x00007ffff753e46a <+106>:	lea    0x128(%rdi),%rdx
   0x00007ffff753e471 <+113>:	lea    0x128(%rsi),%rsi
   0x00007ffff753e478 <+120>:	mov    $0x2,%edi
   0x00007ffff753e47d <+125>:	mov    $0x8,%r10d
   0x00007ffff753e483 <+131>:	mov    $0xe,%eax
   0x00007ffff753e488 <+136>:	syscall
   0x00007ffff753e48a <+138>:	cmp    $0xfffffffffffff001,%rax
   0x00007ffff753e490 <+144>:	jae    0x7ffff753e4f0 <swapcontext+240>
   0x00007ffff753e492 <+146>:	mov    %r12,%rsi
   0x00007ffff753e495 <+149>:	mov    0xe0(%rsi),%rcx
   0x00007ffff753e49c <+156>:	fldenv (%rcx)
   0x00007ffff753e49e <+158>:	ldmxcsr 0x1c0(%rsi)
   0x00007ffff753e4a5 <+165>:	mov    0xa0(%rsi),%rsp
   0x00007ffff753e4ac <+172>:	mov    0x80(%rsi),%rbx
   0x00007ffff753e4b3 <+179>:	mov    0x78(%rsi),%rbp
   0x00007ffff753e4b7 <+183>:	mov    0x48(%rsi),%r12
   0x00007ffff753e4bb <+187>:	mov    0x50(%rsi),%r13
   0x00007ffff753e4bf <+191>:	mov    0x58(%rsi),%r14
   0x00007ffff753e4c3 <+195>:	mov    0x60(%rsi),%r15
   0x00007ffff753e4c7 <+199>:	mov    0xa8(%rsi),%rcx
   0x00007ffff753e4ce <+206>:	push   %rcx
   0x00007ffff753e4cf <+207>:	mov    0x68(%rsi),%rdi
   0x00007ffff753e4d3 <+211>:	mov    0x88(%rsi),%rdx
   0x00007ffff753e4da <+218>:	mov    0x98(%rsi),%rcx
   0x00007ffff753e4e1 <+225>:	mov    0x28(%rsi),%r8
   0x00007ffff753e4e5 <+229>:	mov    0x30(%rsi),%r9
   0x00007ffff753e4e9 <+233>:	mov    0x70(%rsi),%rsi
   0x00007ffff753e4ed <+237>:	xor    %eax,%eax
   0x00007ffff753e4ef <+239>:	retq
   0x00007ffff753e4f0 <+240>:	mov    0x37a971(%rip),%rcx        # 0x7ffff78b8e68
   0x00007ffff753e4f7 <+247>:	neg    %eax
   0x00007ffff753e4f9 <+249>:	mov    %eax,%fs:(%rcx)
   0x00007ffff753e4fc <+252>:	or     $0xffffffffffffffff,%rax
   0x00007ffff753e500 <+256>:	retq
End of assembler dump.
```


## Promise & Future

> Promise与Future来源于函数式编程，是一种分离计算（Promise）与结果（Future）的范式，在并行化中可以更加灵活的进行计算。在分布式计算中，减少通信往返时引起的延迟，同时这种方式可以使异步程序更直观地表达，而后继传递式（continuation-passing）          --[wiki](https://en.wikipedia.org/wiki/Futures_and_promises)

我从字面上理解就是Promise就是一种承诺，保证去计算，在以后（future）会有答案。主要就是将看似并行的代码用线性的思想写出来。比如计算两个数之和, 用传统的方法去写(伪代码)：

```python

atomic int i = 0

def callback():
    i += 1

def GetValue( &rst, callback ):
    rst = net_request_api_latency_2s()
    callback()
    return

def main():
    int a  = 0, b = 0
    thread( GetValue(a, callback) )
    thread( GetValue(b, callback) )
    
    while (i < 2) {}
    
    print(a + b)
```
如果使用Promise与Future 逻辑就不用这么复杂了：
```
def GetValue():
    rst = net_request_api_latency_2s()
    return rst
    
def main():
    Future a = Promise(GetValue)
    Future b = Promise(GetValue)
    
    print(a.get_value() + b.get_value())
```
逻辑非常的清晰。

从实现角度来看主要就是封装一下thread，寄存一下结果，由future等待获取结果。

```C++
template <class T>
class Promise{
    public:
        explicit Promise(function<T (void*)> func, void *arg) {
            ret_ = new T;
            thread t([=](){*ret_ = func(arg);});
            t_ = move(t);
        }
        Future<T> get_furture() {
            return Future<T>(move(t_), ret_);
        }
        thread t_;
        T *ret_;
};
```

```C++
template <class T>
class Future {
    public:
    Future(thread&& t, T *ret):t_(move(t)), ret_(ret){};
    Future(Future<T>&&) = default;
    T get() {
        t_.join();
        return *ret_;
    }
    ~Future() {
        delete ret_;
    }
    thread t_;
    T* ret_;
};
```

实验代码在[GitHub](https://github.com/zhang-boyang/c-concurrent)上可获取